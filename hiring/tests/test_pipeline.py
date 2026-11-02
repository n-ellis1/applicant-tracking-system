import html
import re
from datetime import timedelta
from itertools import count
from urllib.parse import quote

import pytest
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone

from hiring import services
from hiring.models import Application, JobOpening, StageHistoryEntry
from hiring.stages import Stage
from hiring.tests.helpers import make_candidate, make_job

DUPLICATE_ERROR = "This candidate has already applied to this job."
CLOSED_JOB_HTML = "This job is closed and can&#x27;t accept new applications."


def job_url(job):
    return reverse("hiring:pipeline_job", args=[job.pk])


def app_url(application):
    return reverse("hiring:application_detail", args=[application.pk])


def add_url(job):
    return reverse("hiring:job_application_create", args=[job.pk])


@pytest.fixture
def employee(employee_client):
    return User.objects.get(username="employee")


def record(candidate, job, employee):
    return services.create_application(
        candidate=candidate,
        job=job,
        applied_on=timezone.localdate(),
        changed_by=employee,
    )


def progress_steps(content):
    """(classes, label) for each step of the rendered progress indicator."""
    return re.findall(
        r'<li class="(step[^"]*)"[^>]*>\s*<span class="text-xs">([^<]+)</span>',
        content,
    )


def sidebar_count(content, job):
    """The in-progress count shown in the job's sidebar link, or None."""
    # The filter links can target the same job URL; skip them.
    content = re.sub(
        r'<div role="group" aria-label="Job filter".*?</div>', "", content, flags=re.S
    )
    link = re.search(
        rf'<a href="{job_url(job)}\?jobs=\w+"[^>]*>(.*?)</a>', content, re.DOTALL
    )
    text = " ".join(re.sub(r"<[^>]+>", " ", link.group(1)).split())
    match = re.search(r"(\d+) in progress", text)
    return match and int(match.group(1))


_emails = count(1)


def add_application(job, stage=Stage.APPLIED, candidate=None):
    # Moving applications arrives in Phase 8, so create them at their stage.
    if candidate is None:
        candidate = make_candidate(email=f"candidate{next(_emails)}@example.com")
    return Application.objects.create(candidate=candidate, job=job, stage=stage)


def test_landing_page_opens_the_first_open_job_by_title(employee_client):
    make_job(title="Zeta Engineer")
    # Alphabetically first, but closed, so it isn't the landing job.
    make_job(title="Alpha Analyst", status=JobOpening.Status.CLOSED)
    beta = make_job(title="beta Builder")
    make_job(title="Gamma Designer")

    response = employee_client.get(reverse("hiring:pipeline"))

    assert response.status_code == 200
    assert response.context.get("job") == beta
    content = response.content.decode()
    assert f'href="{job_url(beta)}?jobs=open" aria-current="page"' in content


def test_landing_page_without_open_jobs_shows_empty_state_and_closed_jobs_link(
    employee_client,
):
    make_job(title="Closed Role", status=JobOpening.Status.CLOSED)

    response = employee_client.get(reverse("hiring:pipeline"))

    assert response.status_code == 200
    assert response.context.get("job") is None
    content = response.content.decode()
    assert "There are no open jobs." in content
    assert f'href="{reverse("hiring:job_create")}"' in content
    # Closed jobs stay reachable by switching the sidebar filter.
    assert f'href="{reverse("hiring:pipeline")}?jobs=closed"' in content


def test_sidebar_counts_only_active_stage_applications(employee_client):
    busy = make_job(title="Busy Role")
    for stage in [Stage.APPLIED, Stage.INTERVIEW, Stage.OFFER]:
        add_application(busy, stage)
    for stage in [Stage.HIRED, Stage.REJECTED, Stage.WITHDRAWN]:
        add_application(busy, stage)
    closed = make_job(title="Closed Role", status=JobOpening.Status.CLOSED)
    add_application(closed, Stage.SCREENING)
    add_application(closed, Stage.REJECTED)
    empty = make_job(title="Empty Role")

    url = f"{reverse('hiring:pipeline')}?jobs=all"
    content = employee_client.get(url).content.decode()

    assert sidebar_count(content, busy) == 3
    assert sidebar_count(content, closed) == 1
    assert sidebar_count(content, empty) == 0


# Recording an application from the workspace's selected job


def test_job_picker_lists_only_candidates_without_an_application_for_that_job(
    employee_client,
):
    job = make_job(title="Data Analyst")
    elsewhere = make_job(title="Other Role")
    applied = make_candidate(first_name="Jane", last_name="Doe")
    rejected = make_candidate(
        first_name="Rita", last_name="Adams", email="rita@example.com"
    )
    add_application(job, candidate=applied)
    # Any existing application counts, whatever its stage.
    add_application(job, Stage.REJECTED, candidate=rejected)
    applied_elsewhere = make_candidate(
        first_name="Bob", last_name="Brown", email="bob@example.com"
    )
    add_application(elsewhere, candidate=applied_elsewhere)
    never_applied = make_candidate(
        first_name="Carol", last_name="Clark", email="carol@example.com"
    )

    response = employee_client.get(
        reverse("hiring:job_application_create", args=[job.pk])
    )

    offered = list(response.context["form"].fields["candidate"].queryset)
    assert offered == [applied_elsewhere, never_applied]
    content = response.content.decode()
    assert "Bob Brown" in content
    assert "Carol Clark" in content
    assert "Jane Doe" not in content
    assert "Rita Adams" not in content


def test_job_side_save_opens_the_workspace_with_the_new_application_selected(
    employee_client, employee
):
    job = make_job()
    candidate = make_candidate()

    response = employee_client.post(
        add_url(job),
        {"candidate": candidate.pk, "applied_on": timezone.localdate().isoformat()},
        follow=True,
    )

    application = Application.objects.get()
    assert response.redirect_chain == [(app_url(application), 302)]
    assert application.candidate == candidate
    assert application.job == job
    assert application.stage == Stage.APPLIED
    assert application.history.get().changed_by == employee
    assert response.context["selected"] == application
    assert f'href="{app_url(application)}?jobs=open" aria-current="true"' in (
        response.content.decode()
    )


def test_job_side_forged_duplicate_is_refused_even_when_existing_is_withdrawn(
    employee_client, employee
):
    job = make_job()
    candidate = make_candidate()
    existing = record(candidate, job, employee)
    # Moving applications arrives in Phase 8, so set the stage directly.
    Application.objects.filter(pk=existing.pk).update(stage=Stage.WITHDRAWN)

    # A forged POST: the picker would never offer this candidate.
    response = employee_client.post(
        add_url(job),
        {"candidate": candidate.pk, "applied_on": timezone.localdate().isoformat()},
    )

    assert response.status_code == 200
    assert response.context["form"].errors["candidate"] == [DUPLICATE_ERROR]
    assert DUPLICATE_ERROR in response.content.decode()
    assert list(Application.objects.all()) == [existing]
    assert StageHistoryEntry.objects.count() == 1


def test_job_side_page_for_a_closed_job_explains_and_offers_no_form(employee_client):
    make_candidate()
    job = make_job(status=JobOpening.Status.CLOSED, closed_at=timezone.now())

    response = employee_client.get(add_url(job))

    assert response.status_code == 200
    content = response.content.decode()
    assert CLOSED_JOB_HTML in content
    assert 'name="candidate"' not in content
    assert ">Save</button>" not in content


def test_job_side_forged_post_for_a_closed_job_writes_nothing(employee_client):
    candidate = make_candidate()
    job = make_job(status=JobOpening.Status.CLOSED, closed_at=timezone.now())

    response = employee_client.post(
        add_url(job),
        {"candidate": candidate.pk, "applied_on": timezone.localdate().isoformat()},
    )

    assert response.status_code == 200
    assert CLOSED_JOB_HTML in response.content.decode()
    assert Application.objects.count() == 0
    assert StageHistoryEntry.objects.count() == 0


def test_job_side_rejects_a_future_applied_on_date(employee_client):
    candidate = make_candidate()
    tomorrow = timezone.localdate() + timedelta(days=1)

    response = employee_client.post(
        add_url(make_job()),
        {"candidate": candidate.pk, "applied_on": tomorrow.isoformat()},
    )

    assert response.context["form"].errors["applied_on"] == [
        "The applied-on date can't be in the future."
    ]
    assert Application.objects.count() == 0


def test_job_side_picker_shows_each_candidates_email(employee_client):
    make_candidate()

    content = employee_client.get(add_url(make_job())).content.decode()

    assert "Jane Doe (jane.doe@example.com)" in content


# Sidebar and job workspace


def test_sidebar_lists_open_jobs_then_closed_jobs_each_by_title(employee_client):
    zeta = make_job(title="Zeta Engineer")
    alpha = make_job(title="Alpha Analyst", status=JobOpening.Status.CLOSED)
    beta = make_job(title="beta Builder")
    omega = make_job(title="Omega Ops", status=JobOpening.Status.CLOSED)

    url = f"{reverse('hiring:pipeline')}?jobs=all"
    content = employee_client.get(url).content.decode()

    links = [f'href="{job_url(job)}?jobs=all"' for job in [beta, zeta, alpha, omega]]
    positions = [content.index(link) for link in links]
    assert positions == sorted(positions)


def test_job_workspace_shows_that_job_and_only_its_applications(employee_client):
    # A closed job is reachable from the sidebar too.
    job = make_job(title="Closed Role", status=JobOpening.Status.CLOSED)
    own = add_application(job, Stage.SCREENING)
    other = add_application(make_job(title="Other Role"))

    response = employee_client.get(job_url(job))

    assert response.status_code == 200
    assert response.context["job"] == job
    content = response.content.decode()
    assert f'href="{job_url(job)}?jobs=closed" aria-current="page"' in content
    assert f'href="{app_url(own)}?jobs=closed"' in content
    assert f'href="{app_url(other)}' not in content
    assert "Select an application to see its details." in content


def test_unknown_job_workspace_is_not_found(employee_client):
    assert employee_client.get("/pipeline/jobs/999/").status_code == 404


def test_open_job_without_applications_says_so_and_offers_add_application(
    employee_client,
):
    job = make_job()

    content = employee_client.get(job_url(job)).content.decode()

    assert "No applications for this job yet." in content
    assert f'href="{add_url(job)}"' in content


def test_closed_job_without_applications_offers_no_add_application(employee_client):
    job = make_job(status=JobOpening.Status.CLOSED, closed_at=timezone.now())

    content = employee_client.get(job_url(job)).content.decode()

    assert "No applications for this job yet." in content
    assert "new applications can't be added" in content
    assert f'href="{add_url(job)}"' not in content


# The application URL opens the workspace with it selected


def test_application_url_renders_the_workspace_with_it_selected(
    employee_client, employee
):
    job = make_job(title="Data Analyst")
    application = record(
        make_candidate(phone="555-0100", location="Amarillo, TX"), job, employee
    )
    neighbour = record(make_candidate(email="bob@example.com"), job, employee)

    response = employee_client.get(app_url(application))

    assert response.status_code == 200
    assert response.context["job"] == job
    assert response.context["selected"] == application
    content = response.content.decode()
    assert f'href="{job_url(job)}?jobs=open" aria-current="page"' in content
    assert f'href="{app_url(application)}?jobs=open" aria-current="true"' in content
    assert f'href="{app_url(neighbour)}?jobs=open">' in content
    for text in ["jane.doe@example.com", "555-0100", "Amarillo, TX", "Data Analyst"]:
        assert text in content
    today = timezone.localdate()
    assert f"{today:%b} {today.day}, {today.year}" in content
    assert ("step step-primary", "Applied") in progress_steps(content)
    assert 'aria-current="step">\n      <span class="text-xs">Applied' in content
    assert "employee" in content


def test_progress_marks_the_stages_reached_by_an_active_application(
    employee_client,
):
    application = add_application(make_job(), Stage.INTERVIEW)

    content = employee_client.get(app_url(application)).content.decode()

    assert progress_steps(content) == [
        ("step step-primary", "Applied"),
        ("step step-primary", "Screening"),
        ("step step-primary", "Interview"),
        ("step", "Final Review"),
        ("step", "Offer"),
        ("step", "Hired"),
    ]


def test_progress_shows_a_final_outcome_after_the_stage_it_left(
    employee_client, employee
):
    application = record(make_candidate(), make_job(), employee)
    # Moving applications arrives in Phase 8, so write the move directly.
    Application.objects.filter(pk=application.pk).update(stage=Stage.REJECTED)
    StageHistoryEntry.objects.create(
        application=application,
        old_stage=Stage.INTERVIEW,
        new_stage=Stage.REJECTED,
        changed_by=employee,
    )

    content = employee_client.get(app_url(application)).content.decode()

    assert progress_steps(content) == [
        ("step step-primary", "Applied"),
        ("step step-primary", "Screening"),
        ("step step-primary", "Interview"),
        ("step", "Final Review"),
        ("step", "Offer"),
        ("step step-error", "Rejected"),
    ]
    assert "Interview → Rejected" in content


def test_candidate_side_save_opens_the_workspace_with_it_selected(employee_client):
    candidate = make_candidate()
    job = make_job()

    response = employee_client.post(
        reverse("hiring:candidate_application_create", args=[candidate.pk]),
        {"job": job.pk, "applied_on": timezone.localdate().isoformat()},
        follow=True,
    )

    application = Application.objects.get()
    assert response.redirect_chain == [(app_url(application), 302)]
    assert response.context["job"] == job
    assert response.context["selected"] == application


def test_candidate_detail_link_opens_the_workspace_with_it_selected(
    employee_client, employee
):
    candidate = make_candidate()
    application = record(candidate, make_job(), employee)

    detail = employee_client.get(
        reverse("hiring:candidate_detail", args=[candidate.pk])
    ).content.decode()
    assert f'href="{app_url(application)}"' in detail

    content = employee_client.get(app_url(application)).content.decode()
    assert f'href="{app_url(application)}?jobs=open" aria-current="true"' in content


# Real counts on the other pages


def test_jobs_list_counts_only_active_applications(employee_client):
    job = make_job()
    for stage in [Stage.APPLIED, Stage.OFFER, Stage.HIRED, Stage.WITHDRAWN]:
        add_application(job, stage)

    response = employee_client.get(reverse("hiring:job_list"))

    assert [job.in_progress_count for job in response.context["jobs"]] == [2]
    assert '<td class="text-right">2</td>' in response.content.decode()


def test_candidates_list_counts_every_application(employee_client):
    jane = make_candidate()
    add_application(make_job(title="First Role"), candidate=jane)
    add_application(make_job(title="Second Role"), Stage.REJECTED, candidate=jane)
    make_candidate(first_name="Bob", last_name="Brown", email="bob@example.com")

    response = employee_client.get(reverse("hiring:candidate_list"))

    counts = {str(c): c.application_count for c in response.context["candidates"]}
    assert counts == {"Bob Brown": 0, "Jane Doe": 2}


def test_close_job_page_shows_the_active_application_count(employee_client):
    job = make_job()
    for stage in [Stage.SCREENING, Stage.FINAL_REVIEW, Stage.REJECTED]:
        add_application(job, stage)

    response = employee_client.get(reverse("hiring:job_close", args=[job.pk]))

    assert response.context["active_count"] == 2
    assert "<strong>2</strong> active applications" in response.content.decode()


# Sidebar filter


def with_filter(url, jobs):
    return f"{url}?jobs={jobs}"


def filter_links(content):
    """(href, label) for each link in the sidebar's job filter."""
    group = re.search(
        r'<div role="group" aria-label="Job filter"[^>]*>(.*?)</div>',
        content,
        re.DOTALL,
    )
    if group is None:
        return []
    return re.findall(r'<a href="([^"]+)"[^>]*>\s*(\w+)\s*</a>', group.group(1))


def show_all_link(content):
    """The href of the hidden-job note's Show all jobs link, or None."""
    match = re.search(r'<a href="([^"]+)"[^>]*>\s*Show all jobs\s*</a>', content)
    return match and match.group(1)


def test_sidebar_filter_defaults_to_open_on_landing_and_to_the_job_status_directly(
    employee_client,
):
    open_job = make_job(title="Alpha Open")
    closed_job = make_job(title="Beta Closed", status=JobOpening.Status.CLOSED)
    application = add_application(closed_job, Stage.SCREENING)

    landing = employee_client.get(reverse("hiring:pipeline")).content.decode()
    job_page = employee_client.get(job_url(closed_job)).content.decode()
    app_page = employee_client.get(app_url(application)).content.decode()

    # The landing page shows only open jobs.
    assert f'href="{with_filter(job_url(open_job), "open")}" aria-current="page"' in (
        landing
    )
    assert f'href="{job_url(closed_job)}' not in landing
    # A closed job's own URLs show closed jobs, so its link is visible.
    for content in [job_page, app_page]:
        current = with_filter(job_url(closed_job), "closed")
        assert f'href="{current}" aria-current="page"' in content
        assert f'href="{job_url(open_job)}' not in content


def test_filter_hiding_the_selected_job_keeps_the_display_and_explains(
    employee_client,
):
    job = make_job(title="Data Analyst")
    application = add_application(job, candidate=make_candidate())
    make_job(title="Old Role", status=JobOpening.Status.CLOSED)

    response = employee_client.get(with_filter(app_url(application), "closed"))

    # The displayed job and application come from the URL, not the filter.
    assert response.status_code == 200
    assert response.context["job"] == job
    assert response.context["selected"] == application
    content = response.content.decode()
    selected_link = with_filter(app_url(application), "closed")
    assert f'href="{selected_link}" aria-current="true"' in content
    assert "jane.doe@example.com" in content
    # The open job's sidebar link is hidden, and the sidebar says why.
    assert f'href="{job_url(job)}?jobs=' not in content
    assert "Data Analyst is open, so the Closed filter hides it." in content


def test_filter_links_keep_the_current_selection(employee_client):
    landing_job = make_job(title="Alpha Open")
    closed_job = make_job(title="Beta Closed", status=JobOpening.Status.CLOSED)
    application = add_application(closed_job, Stage.INTERVIEW)
    landing = reverse("hiring:pipeline")

    # Each page, and the URL its filter links must keep. On the landing page
    # that's the landing job's URL, so a filter change can't pick another job.
    cases = [
        (landing, job_url(landing_job)),
        (with_filter(landing, "closed"), job_url(landing_job)),
        (job_url(closed_job), job_url(closed_job)),
        (app_url(application), app_url(application)),
        (with_filter(app_url(application), "open"), app_url(application)),
    ]
    for page, target in cases:
        content = employee_client.get(page).content.decode()
        assert filter_links(content) == [
            (with_filter(target, "open"), "Open"),
            (with_filter(target, "closed"), "Closed"),
            (with_filter(target, "all"), "All"),
        ], page

    # When the filter hides the selected job, Show all jobs keeps it too.
    hidden_landing = employee_client.get(with_filter(landing, "closed"))
    assert show_all_link(hidden_landing.content.decode()) == with_filter(
        job_url(landing_job), "all"
    )
    hidden_app = employee_client.get(with_filter(app_url(application), "open"))
    assert show_all_link(hidden_app.content.decode()) == with_filter(
        app_url(application), "all"
    )


def active_filter(content):
    match = re.search(
        r'\?jobs=(\w+)"[^>]*aria-current="true"[^>]*>\s*\w+\s*</a>', content
    )
    return match and match.group(1)


def test_unknown_filter_value_falls_back_to_the_page_default(employee_client):
    open_job = make_job(title="Alpha Open")
    closed_job = make_job(title="Beta Closed", status=JobOpening.Status.CLOSED)

    landing = employee_client.get(with_filter(reverse("hiring:pipeline"), "bogus"))
    job_page = employee_client.get(with_filter(job_url(closed_job), "bogus"))

    content = landing.content.decode()
    assert landing.context["jobs_filter"] == "open"
    assert active_filter(content) == "open"
    assert f'href="{with_filter(job_url(open_job), "open")}" aria-current="page"' in (
        content
    )
    assert f'href="{job_url(closed_job)}?jobs=' not in content
    content = job_page.content.decode()
    assert job_page.context["jobs_filter"] == "closed"
    assert active_filter(content) == "closed"
    assert f'href="{with_filter(job_url(closed_job), "closed")}"' in content
    assert "bogus" not in content


def test_all_filter_is_carried_in_sidebar_and_application_links(employee_client):
    open_job = make_job(title="Alpha Open")
    closed_job = make_job(title="Beta Closed", status=JobOpening.Status.CLOSED)
    selected = add_application(open_job)
    neighbour = add_application(open_job)

    response = employee_client.get(with_filter(app_url(selected), "all"))

    content = response.content.decode()
    assert active_filter(content) == "all"
    assert f'href="{with_filter(job_url(open_job), "all")}" aria-current="page"' in (
        content
    )
    assert f'href="{with_filter(job_url(closed_job), "all")}"' in content
    assert f'href="{with_filter(app_url(selected), "all")}" aria-current="true"' in (
        content
    )
    assert f'href="{with_filter(app_url(neighbour), "all")}"' in content
    # Both statuses are visible, so nothing is hidden.
    assert "filter hides it" not in content
    assert show_all_link(content) is None


def test_closed_filter_is_carried_on_an_open_jobs_application_links(employee_client):
    job = make_job(title="Data Analyst")
    application = add_application(job)

    content = employee_client.get(with_filter(job_url(job), "closed")).content.decode()

    assert active_filter(content) == "closed"
    assert f'href="{with_filter(app_url(application), "closed")}"' in content


def test_empty_state_filter_links_target_the_landing_page(employee_client):
    closed_job = make_job(title="Beta Closed", status=JobOpening.Status.CLOSED)
    landing = reverse("hiring:pipeline")

    default = employee_client.get(landing).content.decode()
    closed = employee_client.get(with_filter(landing, "closed"))

    assert filter_links(default) == [
        (with_filter(landing, "open"), "Open"),
        (with_filter(landing, "closed"), "Closed"),
        (with_filter(landing, "all"), "All"),
    ]
    assert f'href="{job_url(closed_job)}?jobs=' not in default
    # Show closed jobs lists them, still with no job selected or hidden.
    content = closed.content.decode()
    assert closed.context["job"] is None
    assert "There are no open jobs." in content
    assert f'href="{with_filter(job_url(closed_job), "closed")}">' in content
    assert "filter hides it" not in content


# Workspace header: close and reopen job


def close_link(content):
    """The href of the workspace header's Close job link, or None."""
    match = re.search(r'<a href="([^"]+)"[^>]*>\s*Close job\s*</a>', content)
    return match and html.unescape(match.group(1))


def reopen_form(content):
    """(action, next) of the workspace header's Reopen job form, or None."""
    match = re.search(
        r'<form method="post" action="([^"]+)">(?:(?!</form>).)*?'
        r'name="next" value="([^"]+)">(?:(?!</form>).)*?Reopen job',
        content,
        re.DOTALL,
    )
    return match and (match.group(1), html.unescape(match.group(2)))


def test_close_and_reopen_from_the_header_return_to_the_same_application(
    employee_client,
):
    job = make_job(title="Data Analyst")
    application = add_application(job)
    here = with_filter(app_url(application), "all")
    close_url = reverse("hiring:job_close", args=[job.pk])

    page = employee_client.get(here).content.decode()
    assert close_link(page) == f"{close_url}?next={quote(here)}"
    assert "Reopen job" not in page

    # The confirmation page carries the return address and uses it for Cancel.
    confirm = employee_client.get(close_link(page)).content.decode()
    assert f'name="next" value="{html.escape(here)}"' in confirm
    assert f'href="{html.escape(here)}" class="btn btn-ghost">Cancel' in confirm

    response = employee_client.post(close_url, {"next": here})
    assert response.url == here
    page = employee_client.get(here).content.decode()
    assert close_link(page) is None
    assert reopen_form(page) == (reverse("hiring:job_reopen", args=[job.pk]), here)

    response = employee_client.post(reopen_form(page)[0], {"next": here})
    assert response.url == here
    job.refresh_from_db()
    assert job.status == JobOpening.Status.OPEN
    assert job.closed_at is None


@pytest.mark.parametrize(
    ("page", "expected"),
    [
        # The landing page returns to its job, so closing can't switch jobs.
        (lambda job, app: reverse("hiring:pipeline"), "job?jobs=open"),
        (lambda job, app: with_filter(job_url(job), "closed"), "job?jobs=closed"),
        (lambda job, app: app_url(app), "app?jobs=open"),
    ],
    ids=["landing", "job", "application"],
)
def test_header_close_returns_to_the_displayed_job_or_application_and_filter(
    employee_client, page, expected
):
    job = make_job(title="Data Analyst")
    application = add_application(job)
    base, query = expected.split("?")
    target = (job_url(job) if base == "job" else app_url(application)) + "?" + query

    content = employee_client.get(page(job, application)).content.decode()

    close_url = reverse("hiring:job_close", args=[job.pk])
    assert close_link(content) == f"{close_url}?next={quote(target)}"


def test_header_after_a_failed_move_returns_to_the_application_not_the_move_url(
    employee_client, employee
):
    job = make_job(title="Data Analyst")
    application = record(make_candidate(), job, employee)
    move_url = reverse("hiring:application_move", args=[application.pk])

    response = employee_client.post(f"{move_url}?jobs=all", {"stage": "bogus"})

    target = with_filter(app_url(application), "all")
    close_url = reverse("hiring:job_close", args=[job.pk])
    assert close_link(response.content.decode()) == f"{close_url}?next={quote(target)}"


def test_header_reopen_leaves_finished_applications_finished(employee_client, employee):
    job = make_job(title="Data Analyst")
    rejected = record(make_candidate(), job, employee)
    services.move_application(rejected, Stage.REJECTED, changed_by=employee)
    services.close_job(job)
    here = app_url(rejected)

    employee_client.post(reverse("hiring:job_reopen", args=[job.pk]), {"next": here})

    assert Application.objects.get(pk=rejected.pk).stage == Stage.REJECTED
    assert rejected.history.count() == 2
    # Reopening the job makes reopening the application possible again.
    page = html.unescape(employee_client.get(here).content.decode())
    assert "Reopen to Applied" in page
