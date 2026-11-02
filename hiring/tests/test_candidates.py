import re
from html import unescape
from urllib.parse import parse_qs, urlsplit

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.urls import reverse

from hiring.models import Candidate
from hiring.tests.helpers import make_candidate

VALID_CANDIDATE = {
    "first_name": "Jane",
    "last_name": "Doe",
    "email": "jane.doe@example.com",
    "phone": "",
    "location": "",
    "profile_url": "",
    "source": "referral",
    "source_details": "",
    "notes": "",
}


def test_creating_a_candidate_stores_the_email_trimmed_and_lowercased(
    employee_client,
):
    response = employee_client.post(
        reverse("hiring:candidate_create"),
        VALID_CANDIDATE | {"email": "  Jane.Doe@Example.com "},
    )

    assert response.status_code == 302
    assert list(Candidate.objects.values_list("email", flat=True)) == [
        "jane.doe@example.com"
    ]


def listed_names(response):
    return [str(candidate) for candidate in response.context["candidates"]]


def test_candidate_search_matches_first_name_ignoring_case(employee_client):
    make_candidate(first_name="Jane", last_name="Doe", email="jd@example.com")
    make_candidate(first_name="Sam", last_name="Rivera", email="sr@example.com")

    response = employee_client.get(reverse("hiring:candidate_list"), {"q": " JAN "})

    assert listed_names(response) == ["Jane Doe"]


def test_candidate_search_matches_last_name_ignoring_case(employee_client):
    make_candidate(first_name="Jane", last_name="Doe", email="jd@example.com")
    make_candidate(first_name="Sam", last_name="Rivera", email="sr@example.com")

    response = employee_client.get(reverse("hiring:candidate_list"), {"q": " RIV "})

    assert listed_names(response) == ["Sam Rivera"]


def test_candidate_search_matches_email_ignoring_case(employee_client):
    make_candidate(first_name="Jane", last_name="Doe", email="jd@acme.test")
    make_candidate(first_name="Sam", last_name="Rivera", email="sr@example.com")

    response = employee_client.get(reverse("hiring:candidate_list"), {"q": " ACME "})

    assert listed_names(response) == ["Jane Doe"]


# The model's ordering was added while scaffolding, so this regression test
# passed on its first run rather than going from RED to GREEN.
def test_candidate_list_sorts_by_last_name_then_first_name(employee_client):
    make_candidate(first_name="Sam", last_name="Rivera", email="sr@example.com")
    make_candidate(first_name="Zoe", last_name="Doe", email="zd@example.com")
    make_candidate(first_name="Adam", last_name="Doe", email="ad@example.com")
    make_candidate(first_name="Ann", last_name="brown", email="ab@example.com")

    response = employee_client.get(reverse("hiring:candidate_list"))

    assert listed_names(response) == ["Ann brown", "Adam Doe", "Zoe Doe", "Sam Rivera"]


DUPLICATE_ERROR = ["A candidate with this email already exists."]


@pytest.fixture
def admin_client_logged_in(client, db):
    client.force_login(User.objects.create_superuser(username="admin", password="pw"))
    return client


def next_page_link(content):
    """The href of the rendered next-page link, or None if there isn't one."""
    match = re.search(r'<a href="([^"]*)" rel="next"', content)
    return unescape(match.group(1)) if match else None


# Creating candidates: fields, choices and duplicate emails


def test_creating_a_candidate_saves_every_field(employee_client):
    response = employee_client.post(
        reverse("hiring:candidate_create"),
        VALID_CANDIDATE
        | {
            "first_name": " Jane ",
            "phone": "555-0100",
            "location": "Amarillo, TX",
            "profile_url": "https://example.com/jane",
            "source": "job_board",
            "source_details": "Indeed",
            "notes": "Strong portfolio.",
        },
    )

    candidate = Candidate.objects.get()
    assert response.status_code == 302
    assert response.url == reverse("hiring:candidate_detail", args=[candidate.pk])
    assert candidate.first_name == "Jane"
    assert candidate.phone == "555-0100"
    assert candidate.location == "Amarillo, TX"
    assert candidate.profile_url == "https://example.com/jane"
    assert candidate.source == Candidate.Source.JOB_BOARD
    assert candidate.source_details == "Indeed"
    assert candidate.notes == "Strong portfolio."


@pytest.mark.parametrize("field", ["first_name", "last_name", "email", "source"])
def test_creating_a_candidate_requires_core_fields(employee_client, field):
    response = employee_client.post(
        reverse("hiring:candidate_create"), VALID_CANDIDATE | {field: "  "}
    )

    assert response.status_code == 200
    assert response.context["form"].errors[field]
    assert not Candidate.objects.exists()


def test_optional_fields_can_be_left_blank(employee_client):
    response = employee_client.post(reverse("hiring:candidate_create"), VALID_CANDIDATE)

    assert response.status_code == 302
    assert Candidate.objects.count() == 1


def test_source_offers_exactly_the_four_fixed_choices(employee_client):
    response = employee_client.get(reverse("hiring:candidate_create"))

    choices = [
        label for value, label in response.context["form"].fields["source"].choices
    ]
    assert choices[1:] == ["Company Website", "Job Board", "Referral", "Other"]


def test_an_unknown_source_is_rejected(employee_client):
    response = employee_client.post(
        reverse("hiring:candidate_create"), VALID_CANDIDATE | {"source": "billboard"}
    )

    assert response.status_code == 200
    assert response.context["form"].errors["source"]
    assert not Candidate.objects.exists()


@pytest.mark.parametrize("field", ["email", "profile_url"])
def test_invalid_email_or_profile_url_is_rejected(employee_client, field):
    response = employee_client.post(
        reverse("hiring:candidate_create"), VALID_CANDIDATE | {field: "not a url"}
    )

    assert response.context["form"].errors[field]
    assert not Candidate.objects.exists()


@pytest.mark.parametrize(
    "duplicate_email",
    ["JANE.DOE@example.com", "  jane.doe@example.com ", " Jane.Doe@EXAMPLE.com"],
)
def test_creating_a_case_or_space_duplicate_email_shows_a_form_error(
    employee_client, duplicate_email
):
    make_candidate(email="jane.doe@example.com")

    response = employee_client.post(
        reverse("hiring:candidate_create"),
        VALID_CANDIDATE | {"first_name": "Other", "email": duplicate_email},
    )

    assert response.status_code == 200
    assert response.context["form"].errors["email"] == DUPLICATE_ERROR
    assert Candidate.objects.count() == 1


@pytest.mark.django_db
def test_database_rejects_a_case_insensitive_duplicate_email_without_the_form():
    make_candidate(email="jane.doe@example.com")

    with pytest.raises(IntegrityError), transaction.atomic():
        make_candidate(first_name="Other", email="JANE.DOE@example.com")

    assert Candidate.objects.count() == 1


# Editing candidates


def test_editing_a_candidate_to_another_candidates_email_shows_a_form_error(
    employee_client,
):
    make_candidate(email="jane.doe@example.com")
    sam = make_candidate(first_name="Sam", last_name="Rivera", email="sr@example.com")

    response = employee_client.post(
        reverse("hiring:candidate_edit", args=[sam.pk]),
        VALID_CANDIDATE
        | {
            "first_name": "Sam",
            "last_name": "Rivera",
            "email": "  JANE.DOE@Example.com ",
        },
    )

    assert response.status_code == 200
    assert response.context["form"].errors["email"] == DUPLICATE_ERROR
    sam.refresh_from_db()
    assert sam.email == "sr@example.com"


@pytest.mark.parametrize(
    "own_email", ["jane.doe@example.com", " JANE.DOE@Example.COM  "]
)
def test_editing_a_candidate_keeping_their_own_email_saves(employee_client, own_email):
    jane = make_candidate(email="jane.doe@example.com")

    response = employee_client.post(
        reverse("hiring:candidate_edit", args=[jane.pk]),
        VALID_CANDIDATE | {"email": own_email, "location": "Canyon, TX"},
    )

    assert response.status_code == 302
    assert response.url == reverse("hiring:candidate_detail", args=[jane.pk])
    jane.refresh_from_db()
    assert jane.email == "jane.doe@example.com"
    assert jane.location == "Canyon, TX"


def test_editing_a_candidate_normalizes_a_changed_email(employee_client):
    jane = make_candidate(email="jane.doe@example.com")

    employee_client.post(
        reverse("hiring:candidate_edit", args=[jane.pk]),
        VALID_CANDIDATE | {"email": "  Jane@NewMail.com "},
    )

    jane.refresh_from_db()
    assert jane.email == "jane@newmail.com"


def test_edit_page_shows_the_current_values(employee_client):
    jane = make_candidate(phone="555-0100")

    response = employee_client.get(reverse("hiring:candidate_edit", args=[jane.pk]))

    content = response.content.decode()
    assert response.status_code == 200
    assert 'value="jane.doe@example.com"' in content
    assert 'value="555-0100"' in content


def test_editing_a_candidate_keeps_their_source_unless_changed(employee_client):
    jane = make_candidate(source=Candidate.Source.REFERRAL)

    employee_client.post(
        reverse("hiring:candidate_edit", args=[jane.pk]),
        VALID_CANDIDATE | {"source": "referral", "notes": "Updated."},
    )

    jane.refresh_from_db()
    assert jane.source == Candidate.Source.REFERRAL
    assert jane.notes == "Updated."


# Candidates list: columns, paging and search in page links


def test_candidate_list_shows_name_email_source_and_application_count(
    employee_client,
):
    jane = make_candidate(source=Candidate.Source.JOB_BOARD)

    content = employee_client.get(reverse("hiring:candidate_list")).content.decode()

    assert "Doe, Jane" in content
    assert "jane.doe@example.com" in content
    assert "Job Board" in content
    assert "Applications" in content
    assert f'href="{reverse("hiring:candidate_detail", args=[jane.pk])}"' in content
    assert f'href="{reverse("hiring:candidate_create")}"' in content


def test_candidate_list_shows_25_per_page(employee_client):
    for number in range(30):
        make_candidate(last_name=f"Doe{number:02}", email=f"c{number}@example.com")

    first = employee_client.get(reverse("hiring:candidate_list"))
    second = employee_client.get(reverse("hiring:candidate_list"), {"page": 2})

    assert len(first.context["candidates"]) == 25
    assert len(second.context["candidates"]) == 5


def test_candidate_list_next_page_link_keeps_the_search(employee_client):
    for number in range(30):
        make_candidate(last_name=f"Doe{number:02}", email=f"c{number}@example.com")

    response = employee_client.get(reverse("hiring:candidate_list"), {"q": " doe "})

    link = next_page_link(response.content.decode())
    assert link is not None, "expected a next-page link"
    assert parse_qs(urlsplit(link).query) == {"q": ["doe"], "page": ["2"]}
    assert 'value="doe"' in response.content.decode()


def test_candidate_list_next_page_link_without_a_search(employee_client):
    for number in range(30):
        make_candidate(last_name=f"Doe{number:02}", email=f"c{number}@example.com")

    response = employee_client.get(reverse("hiring:candidate_list"))

    link = next_page_link(response.content.decode())
    assert parse_qs(urlsplit(link).query) == {"page": ["2"]}


def test_candidate_search_with_no_matches_says_so(employee_client):
    make_candidate()

    response = employee_client.get(reverse("hiring:candidate_list"), {"q": "zzz"})

    assert listed_names(response) == []
    assert "No candidates match." in response.content.decode()


# Candidate detail and delete


def test_candidate_detail_shows_every_field_with_edit_and_delete_links(
    employee_client,
):
    jane = make_candidate(
        phone="555-0100",
        location="Amarillo, TX",
        profile_url="https://example.com/jane",
        source=Candidate.Source.REFERRAL,
        source_details="Referred by Sam",
        notes="Strong portfolio.",
    )

    response = employee_client.get(reverse("hiring:candidate_detail", args=[jane.pk]))

    content = response.content.decode()
    for text in [
        "Jane Doe",
        "jane.doe@example.com",
        "555-0100",
        "Amarillo, TX",
        "https://example.com/jane",
        "Referral",
        "Referred by Sam",
        "Strong portfolio.",
    ]:
        assert text in content
    assert f'href="{reverse("hiring:candidate_edit", args=[jane.pk])}"' in content
    assert f'href="{reverse("hiring:candidate_delete", args=[jane.pk])}"' in content


def test_delete_page_asks_for_confirmation_without_deleting(employee_client):
    jane = make_candidate()

    response = employee_client.get(reverse("hiring:candidate_delete", args=[jane.pk]))

    assert response.status_code == 200
    assert "Jane Doe" in response.content.decode()
    assert Candidate.objects.filter(pk=jane.pk).exists()


def test_confirming_delete_removes_a_candidate_without_applications(employee_client):
    jane = make_candidate()

    response = employee_client.post(reverse("hiring:candidate_delete", args=[jane.pk]))

    assert response.status_code == 302
    assert response.url == reverse("hiring:candidate_list")
    assert not Candidate.objects.exists()


@pytest.mark.parametrize(
    "name", ["candidate_detail", "candidate_edit", "candidate_delete"]
)
def test_missing_candidate_returns_404(employee_client, name):
    response = employee_client.get(reverse(f"hiring:{name}", args=[999]))

    assert response.status_code == 404


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url",
    [
        reverse("hiring:candidate_create"),
        reverse("hiring:candidate_detail", args=[1]),
        reverse("hiring:candidate_edit", args=[1]),
        reverse("hiring:candidate_delete", args=[1]),
    ],
)
def test_anonymous_visitor_is_redirected_from_candidate_pages(client, url):
    response = client.get(url)

    assert response.status_code == 302
    assert response.url == f"{reverse('login')}?next={url}"


# Django admin shares the app's email normalization and duplicate check.


def admin_candidate(**fields):
    return VALID_CANDIDATE | fields


def test_admin_add_trims_and_lowercases_the_email(admin_client_logged_in):
    response = admin_client_logged_in.post(
        reverse("admin:hiring_candidate_add"),
        admin_candidate(email="  Jane.Doe@Example.com "),
    )

    assert response.status_code == 302
    assert list(Candidate.objects.values_list("email", flat=True)) == [
        "jane.doe@example.com"
    ]


def test_admin_add_rejects_a_case_or_space_duplicate_email(admin_client_logged_in):
    make_candidate(email="jane.doe@example.com")

    response = admin_client_logged_in.post(
        reverse("admin:hiring_candidate_add"),
        admin_candidate(first_name="Other", email=" JANE.DOE@example.com "),
    )

    assert response.status_code == 200
    assert response.context["adminform"].form.errors["email"] == DUPLICATE_ERROR
    assert Candidate.objects.count() == 1


def test_admin_change_allows_its_own_email_in_different_case(admin_client_logged_in):
    jane = make_candidate(email="jane.doe@example.com")

    response = admin_client_logged_in.post(
        reverse("admin:hiring_candidate_change", args=[jane.pk]),
        admin_candidate(email="JANE.DOE@example.com"),
    )

    assert response.status_code == 302
    jane.refresh_from_db()
    assert jane.email == "jane.doe@example.com"


def test_admin_change_rejects_another_candidates_email(admin_client_logged_in):
    make_candidate(email="jane.doe@example.com")
    sam = make_candidate(first_name="Sam", last_name="Rivera", email="sr@example.com")

    response = admin_client_logged_in.post(
        reverse("admin:hiring_candidate_change", args=[sam.pk]),
        admin_candidate(
            first_name="Sam", last_name="Rivera", email=" JANE.DOE@EXAMPLE.COM"
        ),
    )

    assert response.status_code == 200
    assert response.context["adminform"].form.errors["email"] == DUPLICATE_ERROR
    sam.refresh_from_db()
    assert sam.email == "sr@example.com"
