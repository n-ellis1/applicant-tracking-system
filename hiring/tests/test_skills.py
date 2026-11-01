import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.urls import reverse

from hiring.models import JobOpening, Skill
from hiring.tests.helpers import make_job


@pytest.mark.parametrize("duplicate_name", ["python", "  Python  ", " PYTHON"])
def test_creating_a_case_or_space_duplicate_shows_a_form_error(
    employee_client, duplicate_name
):
    Skill.objects.create(name="Python")

    response = employee_client.post(
        reverse("hiring:skill_create"), {"name": duplicate_name}
    )

    assert response.status_code == 200
    assert response.context["form"].errors["name"] == [
        "A skill with this name already exists."
    ]
    assert Skill.objects.count() == 1


def test_renaming_a_skill_to_its_own_name_in_different_case_saves(employee_client):
    skill = Skill.objects.create(name="Python")

    response = employee_client.post(
        reverse("hiring:skill_edit", args=[skill.pk]), {"name": "python"}
    )

    assert response.status_code == 302
    assert response.url == reverse("hiring:skill_list")
    skill.refresh_from_db()
    assert skill.name == "python"


@pytest.mark.django_db
def test_database_rejects_a_case_insensitive_duplicate_without_the_form():
    Skill.objects.create(name="Python")

    with pytest.raises(IntegrityError), transaction.atomic():
        Skill.objects.create(name="PYTHON")

    assert Skill.objects.count() == 1


DUPLICATE_ERROR = ["A skill with this name already exists."]


@pytest.fixture
def admin_client_logged_in(client, db):
    client.force_login(User.objects.create_superuser(username="admin", password="pw"))
    return client


def test_skills_are_listed_alphabetically_ignoring_case(employee_client):
    for name in ["banana", "Cherry", "apple", "Django"]:
        Skill.objects.create(name=name)

    response = employee_client.get(reverse("hiring:skill_list"))

    names = [skill.name for skill in response.context["skills"]]
    assert names == ["apple", "banana", "Cherry", "Django"]
    content = response.content.decode()
    assert content.index("apple") < content.index("banana") < content.index("Cherry")


def test_skill_list_links_to_create_rename_and_delete(employee_client):
    skill = Skill.objects.create(name="Python")

    content = employee_client.get(reverse("hiring:skill_list")).content.decode()

    assert f'href="{reverse("hiring:skill_create")}"' in content
    assert f'href="{reverse("hiring:skill_edit", args=[skill.pk])}"' in content
    assert f'href="{reverse("hiring:skill_delete", args=[skill.pk])}"' in content


def test_creating_a_skill_trims_the_name(employee_client):
    response = employee_client.post(reverse("hiring:skill_create"), {"name": "  Go  "})

    assert response.status_code == 302
    assert response.url == reverse("hiring:skill_list")
    assert list(Skill.objects.values_list("name", flat=True)) == ["Go"]


def test_creating_a_skill_requires_a_name(employee_client):
    response = employee_client.post(reverse("hiring:skill_create"), {"name": "   "})

    assert response.status_code == 200
    assert response.context["form"].errors["name"]
    assert not Skill.objects.exists()


def test_renaming_a_skill_trims_the_name(employee_client):
    skill = Skill.objects.create(name="Rust")

    employee_client.post(
        reverse("hiring:skill_edit", args=[skill.pk]), {"name": "  Rust Lang "}
    )

    skill.refresh_from_db()
    assert skill.name == "Rust Lang"


def test_renaming_a_skill_to_another_skills_name_shows_a_form_error(employee_client):
    Skill.objects.create(name="Python")
    skill = Skill.objects.create(name="Pyhton")

    response = employee_client.post(
        reverse("hiring:skill_edit", args=[skill.pk]), {"name": " PYTHON "}
    )

    assert response.status_code == 200
    assert response.context["form"].errors["name"] == DUPLICATE_ERROR
    skill.refresh_from_db()
    assert skill.name == "Pyhton"


def test_rename_page_shows_the_current_name(employee_client):
    skill = Skill.objects.create(name="Python")

    response = employee_client.get(reverse("hiring:skill_edit", args=[skill.pk]))

    assert response.status_code == 200
    assert 'value="Python"' in response.content.decode()


def test_delete_page_asks_for_confirmation_without_deleting(employee_client):
    skill = Skill.objects.create(name="Python")

    response = employee_client.get(reverse("hiring:skill_delete", args=[skill.pk]))

    assert response.status_code == 200
    assert "Python" in response.content.decode()
    assert Skill.objects.filter(pk=skill.pk).exists()


def test_confirming_delete_removes_an_unused_skill(employee_client):
    skill = Skill.objects.create(name="Python")

    response = employee_client.post(reverse("hiring:skill_delete", args=[skill.pk]))

    assert response.status_code == 302
    assert response.url == reverse("hiring:skill_list")
    assert not Skill.objects.filter(pk=skill.pk).exists()


@pytest.mark.django_db
def test_queryset_delete_of_a_skill_used_by_a_job_is_refused():
    skill = Skill.objects.create(name="Python")
    job = make_job()
    job.skills.add(skill)

    with pytest.raises(ProtectedError):
        Skill.objects.filter(pk=skill.pk).delete()

    assert Skill.objects.filter(pk=skill.pk).exists()
    assert list(job.skills.all()) == [skill]


@pytest.mark.django_db
def test_a_closed_job_also_protects_its_skills():
    skill = Skill.objects.create(name="Python")
    make_job(status=JobOpening.Status.CLOSED).skills.add(skill)

    with pytest.raises(ProtectedError):
        Skill.objects.filter(pk=skill.pk).delete()
    with pytest.raises(ProtectedError):
        skill.delete()

    assert Skill.objects.filter(pk=skill.pk).exists()


@pytest.mark.django_db
def test_single_delete_of_a_skill_used_by_a_job_is_refused():
    skill = Skill.objects.create(name="Python")
    job = make_job()
    job.skills.add(skill)

    with pytest.raises(ProtectedError):
        skill.delete()

    assert Skill.objects.filter(pk=skill.pk).exists()
    assert list(job.skills.all()) == [skill]


@pytest.mark.django_db
def test_queryset_delete_refuses_everything_if_any_skill_is_used():
    used = Skill.objects.create(name="Python")
    unused = Skill.objects.create(name="Go")
    make_job().skills.add(used)

    with pytest.raises(ProtectedError):
        Skill.objects.all().delete()

    assert set(Skill.objects.all()) == {used, unused}


@pytest.mark.django_db
def test_unused_skill_can_be_deleted_by_single_and_queryset_delete():
    Skill.objects.create(name="Python").delete()
    Skill.objects.create(name="Go")
    Skill.objects.all().delete()

    assert not Skill.objects.exists()


def test_delete_page_for_a_used_skill_explains_which_jobs_use_it(employee_client):
    skill = Skill.objects.create(name="Python")
    job = make_job(title="Backend Developer")
    job.skills.add(skill)

    response = employee_client.get(reverse("hiring:skill_delete", args=[skill.pk]))

    content = response.content.decode()
    assert "can't be deleted" in content
    assert f'href="{reverse("hiring:job_detail", args=[job.pk])}"' in content
    assert "Backend Developer" in content
    assert 'type="submit"' not in content.split("<main")[-1]


def test_posting_delete_for_a_used_skill_is_refused(employee_client):
    skill = Skill.objects.create(name="Python")
    job = make_job()
    job.skills.add(skill)

    response = employee_client.post(reverse("hiring:skill_delete", args=[skill.pk]))

    assert response.status_code == 200
    assert "Backend Developer" in response.content.decode()
    assert Skill.objects.filter(pk=skill.pk).exists()
    assert list(job.skills.all()) == [skill]


def test_missing_skill_returns_404(employee_client):
    response = employee_client.get(reverse("hiring:skill_edit", args=[999]))

    assert response.status_code == 404


# Django admin follows the same trimming and duplicate rules.


def test_admin_add_trims_the_name(admin_client_logged_in):
    response = admin_client_logged_in.post(
        reverse("admin:hiring_skill_add"), {"name": "  Go  "}
    )

    assert response.status_code == 302
    assert list(Skill.objects.values_list("name", flat=True)) == ["Go"]


def test_admin_add_rejects_a_case_or_space_duplicate(admin_client_logged_in):
    Skill.objects.create(name="Python")

    response = admin_client_logged_in.post(
        reverse("admin:hiring_skill_add"), {"name": "  python "}
    )

    assert response.status_code == 200
    assert response.context["adminform"].form.errors["name"] == DUPLICATE_ERROR
    assert Skill.objects.count() == 1


def test_admin_change_trims_and_allows_its_own_name_in_different_case(
    admin_client_logged_in,
):
    skill = Skill.objects.create(name="Python")

    response = admin_client_logged_in.post(
        reverse("admin:hiring_skill_change", args=[skill.pk]), {"name": " python  "}
    )

    assert response.status_code == 302
    skill.refresh_from_db()
    assert skill.name == "python"


def test_admin_change_rejects_another_skills_name(admin_client_logged_in):
    Skill.objects.create(name="Python")
    skill = Skill.objects.create(name="Go")

    response = admin_client_logged_in.post(
        reverse("admin:hiring_skill_change", args=[skill.pk]), {"name": "PYTHON"}
    )

    assert response.status_code == 200
    assert response.context["adminform"].form.errors["name"] == DUPLICATE_ERROR
    skill.refresh_from_db()
    assert skill.name == "Go"


# Admin delete paths refuse used skills, open or closed jobs alike.


def admin_bulk_delete(client, *skills):
    return client.post(
        reverse("admin:hiring_skill_changelist"),
        {
            "action": "delete_selected",
            "_selected_action": [skill.pk for skill in skills],
            "post": "yes",
        },
    )


@pytest.mark.parametrize("status", list(JobOpening.Status))
def test_admin_bulk_delete_of_a_used_skill_is_refused(admin_client_logged_in, status):
    used = Skill.objects.create(name="Python")
    unused = Skill.objects.create(name="Go")
    job = make_job(title="Backend Developer", status=status)
    job.skills.add(used)

    response = admin_bulk_delete(admin_client_logged_in, used, unused)

    assert response.status_code == 200
    content = response.content.decode()
    assert "would require deleting the following protected related objects" in content
    assert "Job opening: Backend Developer" in content
    assert set(Skill.objects.all()) == {used, unused}
    assert list(job.skills.all()) == [used]


def test_admin_bulk_delete_of_unused_skills_works(admin_client_logged_in):
    skills = [Skill.objects.create(name="Python"), Skill.objects.create(name="Go")]

    response = admin_bulk_delete(admin_client_logged_in, *skills)

    assert response.status_code == 302
    assert not Skill.objects.exists()


def test_admin_single_delete_of_a_used_skill_is_refused(admin_client_logged_in):
    skill = Skill.objects.create(name="Python")
    make_job(title="Backend Developer").skills.add(skill)

    response = admin_client_logged_in.post(
        reverse("admin:hiring_skill_delete", args=[skill.pk]), {"post": "yes"}
    )

    assert response.status_code == 200
    assert "Job opening: Backend Developer" in response.content.decode()
    assert Skill.objects.filter(pk=skill.pk).exists()


def test_admin_single_delete_of_an_unused_skill_works(admin_client_logged_in):
    skill = Skill.objects.create(name="Python")

    response = admin_client_logged_in.post(
        reverse("admin:hiring_skill_delete", args=[skill.pk]), {"post": "yes"}
    )

    assert response.status_code == 302
    assert not Skill.objects.exists()
