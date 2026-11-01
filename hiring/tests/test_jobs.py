import re
from datetime import UTC, datetime
from html import unescape
from urllib.parse import parse_qs, urlsplit

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from hiring.models import JobOpening, Skill
from hiring.tests.helpers import make_job

CLOSED = JobOpening.Status.CLOSED

VALID_JOB = {
    "title": "Backend Developer",
    "department": "Engineering",
    "employment_type": "full_time",
    "location": "",
    "description": "Builds APIs.",
}


@pytest.fixture
def admin_client_logged_in(client, db):
    client.force_login(User.objects.create_superuser(username="admin", password="pw"))
    return client


def listed_titles(response):
    return [job.title for job in response.context["jobs"]]


def next_page_link(content):
    """The href of the rendered next-page link, or None if there isn't one."""
    match = re.search(r'<a href="([^"]*)" rel="next"', content)
    return unescape(match.group(1)) if match else None


def test_jobs_list_shows_only_open_jobs_by_default(employee_client):
    make_job(title="Open Role")
    # Closing through the app arrives in Phase 4, so set the status directly.
    make_job(title="Closed Role", status=JobOpening.Status.CLOSED)

    response = employee_client.get(reverse("hiring:job_list"))

    assert [job.title for job in response.context["jobs"]] == ["Open Role"]
    content = response.content.decode()
    assert "Open Role" in content
    assert "Closed Role" not in content


def test_jobs_list_next_page_link_keeps_search_and_filter(employee_client):
    for number in range(30):
        make_job(title=f"Data Engineer {number:02}")

    response = employee_client.get(
        reverse("hiring:job_list"), {"q": "data", "status": "all"}
    )

    link = next_page_link(response.content.decode())
    assert link is not None, "expected a next-page link"
    assert parse_qs(urlsplit(link).query) == {
        "q": ["data"],
        "status": ["all"],
        "page": ["2"],
    }


# Jobs list: filter, search, order and paging


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("open", ["Open Role"]),
        ("closed", ["Closed Role"]),
        ("all", ["Closed Role", "Open Role"]),
        ("bogus", ["Open Role"]),
    ],
)
def test_jobs_list_status_filter(employee_client, status, expected):
    make_job(title="Open Role")
    make_job(title="Closed Role", status=CLOSED)

    response = employee_client.get(reverse("hiring:job_list"), {"status": status})

    assert listed_titles(response) == expected


def test_jobs_list_searches_titles_ignoring_case_and_spaces(employee_client):
    make_job(title="Data Engineer")
    make_job(title="Senior DATA Analyst")
    make_job(title="Designer")

    response = employee_client.get(reverse("hiring:job_list"), {"q": "  data "})

    assert listed_titles(response) == ["Data Engineer", "Senior DATA Analyst"]
    assert 'value="data"' in response.content.decode()


def test_jobs_list_search_and_filter_combine(employee_client):
    make_job(title="Data Engineer")
    make_job(title="Data Analyst", status=CLOSED)

    response = employee_client.get(
        reverse("hiring:job_list"), {"q": "data", "status": "closed"}
    )

    assert listed_titles(response) == ["Data Analyst"]


def test_jobs_list_sorts_by_title_ignoring_case(employee_client):
    for title in ["designer", "Backend Developer", "analyst"]:
        make_job(title=title)

    response = employee_client.get(reverse("hiring:job_list"))

    assert listed_titles(response) == ["analyst", "Backend Developer", "designer"]


def test_jobs_list_shows_25_per_page_and_page_two_keeps_the_filter(employee_client):
    for number in range(30):
        make_job(title=f"Data Engineer {number:02}", status=CLOSED)
    make_job(title="Data Open Role")

    first = employee_client.get(
        reverse("hiring:job_list"), {"q": "data", "status": "closed"}
    )
    second = employee_client.get(
        reverse("hiring:job_list") + next_page_link(first.content.decode())
    )

    assert len(listed_titles(first)) == 25
    assert listed_titles(second) == [f"Data Engineer {n:02}" for n in range(25, 30)]


def test_jobs_list_previous_page_link_keeps_search_and_filter(employee_client):
    for number in range(30):
        make_job(title=f"Data Engineer {number:02}", status=CLOSED)

    response = employee_client.get(
        reverse("hiring:job_list"), {"q": "data", "status": "closed", "page": 2}
    )

    match = re.search(r'<a href="([^"]*)" rel="prev"', response.content.decode())
    assert parse_qs(urlsplit(unescape(match.group(1))).query) == {
        "q": ["data"],
        "status": ["closed"],
        "page": ["1"],
    }


def test_jobs_list_shows_the_job_columns(employee_client):
    make_job(
        title="Data Engineer",
        department="Analytics",
        location="Remote",
        employment_type=JobOpening.EmploymentType.CONTRACT,
    )

    content = employee_client.get(reverse("hiring:job_list")).content.decode()

    headers = re.findall(r"<th[^>]*>([^<]*)</th>", content)
    assert headers == [
        "Title",
        "Department",
        "Location",
        "Type",
        "Status",
        "Closed",
        "Active applications",
    ]
    for text in ["Data Engineer", "Analytics", "Remote", "Contract", "Open"]:
        assert text in content


def test_jobs_list_links_to_each_job_and_to_create(employee_client):
    job = make_job()

    content = employee_client.get(reverse("hiring:job_list")).content.decode()

    assert f'href="{reverse("hiring:job_detail", args=[job.pk])}"' in content
    assert f'href="{reverse("hiring:job_create")}"' in content


# Create and edit


def test_creating_a_job_starts_open_with_skills_and_trimmed_text(employee_client):
    python = Skill.objects.create(name="Python")
    Skill.objects.create(name="Go")

    response = employee_client.post(
        reverse("hiring:job_create"),
        VALID_JOB | {"title": "  Backend Developer ", "skills": [python.pk]},
    )

    job = JobOpening.objects.get()
    assert response.status_code == 302
    assert response.url == reverse("hiring:job_detail", args=[job.pk])
    assert job.title == "Backend Developer"
    assert job.status == JobOpening.Status.OPEN
    assert job.closed_at is None
    assert list(job.skills.all()) == [python]


def test_creating_a_job_without_location_or_skills_is_allowed(employee_client):
    response = employee_client.post(reverse("hiring:job_create"), VALID_JOB)

    assert response.status_code == 302
    job = JobOpening.objects.get()
    assert job.location == ""
    assert not job.skills.exists()


@pytest.mark.parametrize(
    "field", ["title", "department", "employment_type", "description"]
)
def test_creating_a_job_requires_core_fields(employee_client, field):
    response = employee_client.post(
        reverse("hiring:job_create"), VALID_JOB | {field: "   "}
    )

    assert response.status_code == 200
    assert response.context["form"].errors[field]
    assert not JobOpening.objects.exists()


def test_job_form_does_not_offer_status_or_closed_date(employee_client):
    form = employee_client.get(reverse("hiring:job_create")).context["form"]

    assert "status" not in form.fields
    assert "closed_at" not in form.fields


def test_status_posted_to_the_create_form_is_ignored(employee_client):
    employee_client.post(reverse("hiring:job_create"), VALID_JOB | {"status": "closed"})

    assert JobOpening.objects.get().status == JobOpening.Status.OPEN


def test_editing_a_job_changes_details_and_skills(employee_client):
    python = Skill.objects.create(name="Python")
    go = Skill.objects.create(name="Go")
    job = make_job()
    job.skills.add(python)

    response = employee_client.post(
        reverse("hiring:job_edit", args=[job.pk]),
        VALID_JOB | {"title": "Platform Engineer", "skills": [go.pk]},
    )

    assert response.status_code == 302
    assert response.url == reverse("hiring:job_detail", args=[job.pk])
    job.refresh_from_db()
    assert job.title == "Platform Engineer"
    assert list(job.skills.all()) == [go]


def test_editing_a_job_updates_last_updated(employee_client):
    job = make_job()
    earlier = datetime(2026, 1, 1, tzinfo=UTC)
    JobOpening.objects.filter(pk=job.pk).update(updated_at=earlier)

    employee_client.post(reverse("hiring:job_edit", args=[job.pk]), VALID_JOB)

    job.refresh_from_db()
    assert job.updated_at > earlier


def test_edit_page_shows_current_values_and_checked_skills(employee_client):
    python = Skill.objects.create(name="Python")
    job = make_job(title="Data Engineer")
    job.skills.add(python)

    response = employee_client.get(reverse("hiring:job_edit", args=[job.pk]))

    content = response.content.decode()
    assert 'value="Data Engineer"' in content
    assert re.search(rf'value="{python.pk}"[^>]*checked', content)


# Detail


def test_job_detail_shows_skills_and_times_in_central_time(employee_client):
    job = make_job(location="Remote")
    job.skills.add(Skill.objects.create(name="Python"))
    JobOpening.objects.filter(pk=job.pk).update(
        created_at=datetime(2026, 1, 15, 18, 30, tzinfo=UTC),
        updated_at=datetime(2026, 7, 4, 17, 5, tzinfo=UTC),
    )

    content = employee_client.get(
        reverse("hiring:job_detail", args=[job.pk])
    ).content.decode()

    assert "Python" in content
    assert "Remote" in content
    assert "Jan 15, 2026, 12:30 PM CST" in content
    assert "Jul 4, 2026, 12:05 PM CDT" in content


def test_renaming_a_skill_shows_the_new_name_on_every_job(employee_client):
    skill = Skill.objects.create(name="Pyhton")
    jobs = [make_job(title="Backend"), make_job(title="Data", status=CLOSED)]
    for job in jobs:
        job.skills.add(skill)

    employee_client.post(
        reverse("hiring:skill_edit", args=[skill.pk]), {"name": "Python"}
    )

    for job in jobs:
        content = employee_client.get(
            reverse("hiring:job_detail", args=[job.pk])
        ).content.decode()
        assert "Python" in content
        assert "Pyhton" not in content


def test_missing_job_returns_404(employee_client):
    response = employee_client.get(reverse("hiring:job_detail", args=[999]))

    assert response.status_code == 404


# Delete


def test_job_delete_page_asks_for_confirmation_without_deleting(employee_client):
    job = make_job()

    response = employee_client.get(reverse("hiring:job_delete", args=[job.pk]))

    assert response.status_code == 200
    assert "Backend Developer" in response.content.decode()
    assert JobOpening.objects.filter(pk=job.pk).exists()


def test_confirming_delete_removes_the_job_and_keeps_its_skills(employee_client):
    skill = Skill.objects.create(name="Python")
    job = make_job()
    job.skills.add(skill)

    response = employee_client.post(reverse("hiring:job_delete", args=[job.pk]))

    assert response.status_code == 302
    assert response.url == reverse("hiring:job_list")
    assert not JobOpening.objects.exists()
    assert Skill.objects.filter(pk=skill.pk).exists()


# Closing and reopening


def test_closing_a_job_needs_the_confirmation_page_and_a_post(employee_client):
    job = make_job()
    url = reverse("hiring:job_close", args=[job.pk])

    page = employee_client.get(url)

    job.refresh_from_db()
    assert page.status_code == 200
    assert job.status == JobOpening.Status.OPEN
    assert job.closed_at is None

    before = timezone.now()
    employee_client.post(url)

    job.refresh_from_db()
    assert job.status == CLOSED
    assert job.closed_at is not None
    assert before <= job.closed_at <= timezone.now()


def test_closing_an_already_closed_job_changes_nothing(employee_client):
    closed_at = datetime(2026, 3, 1, tzinfo=UTC)
    updated_at = datetime(2026, 3, 2, tzinfo=UTC)
    job = make_job(status=CLOSED)
    JobOpening.objects.filter(pk=job.pk).update(
        closed_at=closed_at, updated_at=updated_at
    )

    employee_client.post(reverse("hiring:job_close", args=[job.pk]))

    job.refresh_from_db()
    assert job.status == CLOSED
    assert job.closed_at == closed_at
    assert job.updated_at == updated_at


def test_reopening_a_job_sets_it_open_and_clears_the_closed_date(employee_client):
    job = make_job(status=CLOSED, closed_at=datetime(2026, 3, 1, tzinfo=UTC))

    employee_client.post(reverse("hiring:job_reopen", args=[job.pk]))

    job.refresh_from_db()
    assert job.status == JobOpening.Status.OPEN
    assert job.closed_at is None


def test_reopening_an_already_open_job_changes_nothing(employee_client):
    updated_at = datetime(2026, 3, 2, tzinfo=UTC)
    job = make_job()
    JobOpening.objects.filter(pk=job.pk).update(updated_at=updated_at)

    employee_client.post(reverse("hiring:job_reopen", args=[job.pk]))

    job.refresh_from_db()
    assert job.status == JobOpening.Status.OPEN
    assert job.closed_at is None
    assert job.updated_at == updated_at


def test_a_get_request_cannot_reopen_a_job(employee_client):
    closed_at = datetime(2026, 3, 1, tzinfo=UTC)
    job = make_job(status=CLOSED, closed_at=closed_at)

    response = employee_client.get(reverse("hiring:job_reopen", args=[job.pk]))

    job.refresh_from_db()
    assert response.status_code == 405
    assert job.status == CLOSED
    assert job.closed_at == closed_at


@pytest.mark.parametrize(
    ("action", "starting_status"),
    [("hiring:job_close", JobOpening.Status.OPEN), ("hiring:job_reopen", CLOSED)],
)
@pytest.mark.parametrize(
    ("next_url", "same_site"),
    [
        ("/jobs/?status=closed", True),
        ("https://evil.example.com/", False),
        ("//evil.example.com/", False),
    ],
)
def test_close_and_reopen_return_only_to_a_same_site_next(
    employee_client, action, starting_status, next_url, same_site
):
    job = make_job(status=starting_status)

    response = employee_client.post(reverse(action, args=[job.pk]), {"next": next_url})

    job_detail = reverse("hiring:job_detail", args=[job.pk])
    assert response.status_code == 302
    assert response.url == (next_url if same_site else job_detail)


def hidden_next(content):
    """The value of the rendered hidden next field, or None if there isn't one."""
    match = re.search(r'<input type="hidden" name="next" value="([^"]*)"', content)
    return unescape(match.group(1)) if match else None


def cancel_link(content):
    match = re.search(r'<a href="([^"]*)" class="btn btn-ghost">Cancel</a>', content)
    return unescape(match.group(1))


def test_close_page_explains_the_effects_on_applications(employee_client):
    job = make_job()

    content = employee_client.get(
        reverse("hiring:job_close", args=[job.pk])
    ).content.decode()

    assert "Backend Developer" in content
    assert "<strong>0</strong> active applications" in content
    assert "keep their current stages" in content
    assert "Only Reject and Mark withdrawn remain available" in content
    assert "New applications are blocked" in content


def test_next_survives_from_the_close_page_through_the_post(employee_client):
    job = make_job()
    next_url = "/jobs/?status=closed&q=data"

    page = employee_client.get(
        reverse("hiring:job_close", args=[job.pk]), {"next": next_url}
    )
    carried = hidden_next(page.content.decode())
    response = employee_client.post(
        reverse("hiring:job_close", args=[job.pk]), {"next": carried}
    )

    assert carried == next_url
    assert response.url == next_url
    job.refresh_from_db()
    assert job.status == CLOSED


def test_close_page_cancel_returns_to_a_same_site_next(employee_client):
    job = make_job()

    content = employee_client.get(
        reverse("hiring:job_close", args=[job.pk]), {"next": "/jobs/?status=all"}
    ).content.decode()

    assert cancel_link(content) == "/jobs/?status=all"


@pytest.mark.parametrize(
    "next_url", [None, "https://evil.example.com/", "//evil.example.com/"]
)
def test_close_page_drops_a_missing_or_off_site_next(employee_client, next_url):
    job = make_job()
    query = {"next": next_url} if next_url else {}

    content = employee_client.get(
        reverse("hiring:job_close", args=[job.pk]), query
    ).content.decode()

    assert hidden_next(content) is None
    assert cancel_link(content) == reverse("hiring:job_detail", args=[job.pk])
    assert "evil.example.com" not in content


def test_open_job_detail_offers_close_and_not_reopen(employee_client):
    job = make_job()

    content = employee_client.get(
        reverse("hiring:job_detail", args=[job.pk])
    ).content.decode()

    assert f'href="{reverse("hiring:job_close", args=[job.pk])}"' in content
    assert reverse("hiring:job_reopen", args=[job.pk]) not in content


def test_closed_job_detail_offers_reopen_as_a_post_and_not_close(employee_client):
    job = make_job(status=CLOSED, closed_at=datetime(2026, 3, 1, tzinfo=UTC))

    content = employee_client.get(
        reverse("hiring:job_detail", args=[job.pk])
    ).content.decode()

    reopen = reverse("hiring:job_reopen", args=[job.pk])
    assert f'<form method="post" action="{reopen}">' in content
    assert reverse("hiring:job_close", args=[job.pk]) not in content


def test_editing_a_closed_job_keeps_status_and_closed_date(employee_client):
    python = Skill.objects.create(name="Python")
    go = Skill.objects.create(name="Go")
    closed_at = datetime(2026, 3, 1, tzinfo=UTC)
    earlier = datetime(2026, 3, 2, tzinfo=UTC)
    job = make_job(status=CLOSED, closed_at=closed_at)
    job.skills.add(python)
    JobOpening.objects.filter(pk=job.pk).update(updated_at=earlier)

    response = employee_client.post(
        reverse("hiring:job_edit", args=[job.pk]),
        VALID_JOB | {"description": "Builds better APIs.", "skills": [go.pk]},
    )

    assert response.status_code == 302
    job.refresh_from_db()
    assert job.description == "Builds better APIs."
    assert list(job.skills.all()) == [go]
    assert job.status == CLOSED
    assert job.closed_at == closed_at
    assert job.updated_at > earlier


def test_closed_date_shows_in_central_time_on_detail_and_list(employee_client):
    # 03:00 UTC on Mar 1 is still Feb 28 in Central time.
    job = make_job(status=CLOSED, closed_at=datetime(2026, 3, 1, 3, 0, tzinfo=UTC))

    detail = employee_client.get(
        reverse("hiring:job_detail", args=[job.pk])
    ).content.decode()
    listing = employee_client.get(
        reverse("hiring:job_list"), {"status": "closed"}
    ).content.decode()

    assert "Feb 28, 2026, 9:00 PM CST" in detail
    assert "<td>Feb 28, 2026</td>" in listing


# Django admin uses the same fields and validation.


def test_admin_add_creates_an_open_job_with_trimmed_title(admin_client_logged_in):
    response = admin_client_logged_in.post(
        reverse("admin:hiring_jobopening_add"),
        VALID_JOB | {"title": " Backend Developer  ", "status": "closed"},
    )

    assert response.status_code == 302
    job = JobOpening.objects.get()
    assert job.title == "Backend Developer"
    assert job.status == JobOpening.Status.OPEN


def test_admin_requires_the_same_core_fields(admin_client_logged_in):
    response = admin_client_logged_in.post(
        reverse("admin:hiring_jobopening_add"), VALID_JOB | {"description": "  "}
    )

    assert response.status_code == 200
    assert response.context["adminform"].form.errors["description"]


def test_admin_change_cannot_edit_status_or_closed_date(admin_client_logged_in):
    job = make_job()

    response = admin_client_logged_in.get(
        reverse("admin:hiring_jobopening_change", args=[job.pk])
    )

    form = response.context["adminform"].form
    assert "status" not in form.fields
    assert "closed_at" not in form.fields
