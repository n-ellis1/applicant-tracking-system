from datetime import timedelta
from urllib.parse import urlencode

import pytest
from django.contrib.auth.models import User
from django.db import DatabaseError
from django.db.models import ProtectedError
from django.db.models.deletion import Collector
from django.urls import reverse
from django.utils import timezone
from django.utils.html import escape

from hiring import services
from hiring.models import MOVED_APPLICATION, Application, StageHistoryEntry
from hiring.stages import Stage
from hiring.tests.helpers import make_candidate, make_job


@pytest.fixture
def employee(db):
    return User.objects.create_user(username="recorder", password="pw")


def record(employee, **candidate_fields):
    return services.create_application(
        candidate=make_candidate(**candidate_fields),
        job=make_job(),
        applied_on=timezone.localdate(),
        changed_by=employee,
    )


# Only never-moved applications can be deleted, along with their initial
# history entry.


def test_queryset_delete_removes_a_never_moved_application_and_its_initial_entry(
    employee,
):
    application = record(employee)

    Application.objects.filter(pk=application.pk).delete()

    assert not Application.objects.filter(pk=application.pk).exists()
    assert not StageHistoryEntry.objects.filter(application_id=application.pk).exists()


def snapshot():
    """Every application and history entry, field by field."""
    return (
        list(Application.objects.order_by("pk").values()),
        list(StageHistoryEntry.objects.order_by("pk").values()),
    )


def test_queryset_delete_including_a_moved_application_is_refused_entirely(employee):
    never_moved = record(employee)
    moved = record(employee, email="sam.lee@example.com")
    services.move_application(moved, Stage.SCREENING, changed_by=employee)
    # Back at Applied, but it has moved, so it stays protected.
    services.move_application(moved, Stage.APPLIED, changed_by=employee)
    before = snapshot()

    with pytest.raises(ProtectedError):
        Application.objects.filter(pk__in=[never_moved.pk, moved.pk]).delete()

    assert snapshot() == before
    applications, entries = before
    assert [a["id"] for a in applications] == [never_moved.pk, moved.pk]
    assert len(entries) == 4


# Django admin follows the same never-moved rule.


@pytest.fixture
def admin_client_logged_in(client, db):
    client.force_login(User.objects.create_superuser(username="admin", password="pw"))
    return client


def test_admin_single_delete_of_a_never_moved_application_works(
    admin_client_logged_in, employee
):
    application = record(employee)
    url = reverse("admin:hiring_application_delete", args=[application.pk])

    page = admin_client_logged_in.get(url)

    assert page.status_code == 200
    content = page.content.decode()
    assert "Are you sure you want to delete" in content
    assert "protected related objects" not in content

    response = admin_client_logged_in.post(url, {"post": "yes"})

    assert response.status_code == 302
    assert not Application.objects.filter(pk=application.pk).exists()
    assert not StageHistoryEntry.objects.filter(application_id=application.pk).exists()


# Model and QuerySet paths


def moved_back_to_applied(employee, **candidate_fields):
    application = record(employee, **candidate_fields)
    services.move_application(application, Stage.SCREENING, changed_by=employee)
    services.move_application(application, Stage.APPLIED, changed_by=employee)
    return application


def test_model_delete_removes_a_never_moved_application_and_its_initial_entry(
    employee,
):
    application = record(employee)
    pk = application.pk

    application.delete()

    assert not Application.objects.filter(pk=pk).exists()
    assert not StageHistoryEntry.objects.filter(application_id=pk).exists()


def test_queryset_delete_removes_several_never_moved_applications(employee):
    record(employee)
    record(employee, email="sam.lee@example.com")

    Application.objects.all().delete()

    assert not Application.objects.exists()
    assert not StageHistoryEntry.objects.exists()


@pytest.mark.parametrize("path", ["model", "queryset"])
def test_application_moved_back_to_applied_cannot_be_deleted(employee, path):
    application = moved_back_to_applied(employee)
    assert application.stage == Stage.APPLIED
    before = snapshot()

    with pytest.raises(ProtectedError) as refusal:
        if path == "model":
            application.delete()
        else:
            Application.objects.filter(pk=application.pk).delete()

    assert refusal.value.args[0] == MOVED_APPLICATION
    assert snapshot() == before


@pytest.mark.parametrize("path", ["model", "queryset"])
def test_failed_application_delete_keeps_the_initial_entry(employee, path, monkeypatch):
    application = record(employee)
    before = snapshot()
    original = Collector.delete

    def fail_on_applications(self):
        # Let the initial entry go, then fail deleting the application.
        if Application in self.data:
            raise DatabaseError("application delete failed")
        return original(self)

    monkeypatch.setattr(Collector, "delete", fail_on_applications)

    with pytest.raises(DatabaseError):
        if path == "model":
            application.delete()
        else:
            Application.objects.filter(pk=application.pk).delete()

    assert snapshot() == before


def test_history_entries_cannot_be_deleted_on_their_own(employee):
    record(employee)
    application = moved_back_to_applied(employee, email="sam.lee@example.com")
    before = snapshot()

    with pytest.raises(ProtectedError):
        application.history.first().delete()
    with pytest.raises(ProtectedError):
        application.history.all().delete()
    with pytest.raises(ProtectedError):
        # Not even an initial entry of a never-moved application.
        StageHistoryEntry.objects.filter(old_stage="").delete()

    assert snapshot() == before


# Deleting through the app


@pytest.fixture
def app_client(client, employee):
    client.force_login(employee)
    return client


def delete_url(application, **query):
    url = reverse("hiring:application_delete", args=[application.pk])
    return f"{url}?{urlencode(query)}" if query else url


def test_delete_page_asks_for_confirmation_without_deleting(app_client, employee):
    application = record(employee)
    next_url = reverse("hiring:pipeline_job", args=[application.job.pk]) + "?jobs=all"

    response = app_client.get(delete_url(application, next=next_url))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Delete application" in content
    assert 'btn-error">Delete</button>' in content
    assert f'name="next" value="{escape(next_url)}"' in content
    assert f'href="{escape(next_url)}" class="btn btn-ghost">Cancel' in content
    assert Application.objects.filter(pk=application.pk).exists()


def test_delete_page_without_next_cancels_to_the_application(app_client, employee):
    application = record(employee)
    detail = reverse("hiring:application_detail", args=[application.pk])

    content = app_client.get(delete_url(application)).content.decode()

    assert f'href="{detail}?tab=all" class="btn btn-ghost">Cancel' in content
    assert 'name="next"' not in content


def test_confirming_delete_removes_the_application_and_returns_to_next(
    app_client, employee
):
    application = record(employee)
    next_url = reverse("hiring:pipeline_job", args=[application.job.pk]) + "?jobs=all"

    response = app_client.post(delete_url(application), {"next": next_url})

    assert response.status_code == 302
    assert response.url == next_url
    assert not Application.objects.exists()
    assert not StageHistoryEntry.objects.exists()


@pytest.mark.parametrize("next_url", ["", "https://evil.example.com/"])
def test_confirming_delete_without_a_safe_next_returns_to_the_job(
    app_client, employee, next_url
):
    application = record(employee)

    response = app_client.post(delete_url(application), {"next": next_url})

    assert response.url == reverse("hiring:pipeline_job", args=[application.job.pk])
    assert not Application.objects.exists()


@pytest.mark.parametrize("method", ["get", "post"])
def test_delete_page_for_a_moved_application_explains_why_it_is_blocked(
    app_client, employee, method
):
    application = moved_back_to_applied(employee)
    before = snapshot()

    response = getattr(app_client, method)(delete_url(application))

    assert response.status_code == 200
    content = response.content.decode()
    assert "Can't delete application" in content
    assert "it has changed stages" in content
    assert 'btn-error">Delete</button>' not in content
    assert snapshot() == before


def test_editing_details_keeps_a_never_moved_application_deletable(
    app_client, employee
):
    application = record(employee)
    app_client.post(
        reverse("hiring:application_details", args=[application.pk]),
        {
            "applied_on": (timezone.localdate() - timedelta(days=3)).isoformat(),
            "notes": "Strong portfolio.",
        },
    )
    application.refresh_from_db()
    assert application.notes == "Strong portfolio."

    response = app_client.post(delete_url(application))

    assert response.status_code == 302
    assert not Application.objects.exists()
    assert not StageHistoryEntry.objects.exists()


def test_closing_the_job_keeps_a_never_moved_application_deletable(
    app_client, employee
):
    # Eligibility comes from history alone, not the job's status.
    application = record(employee)
    services.close_job(application.job)
    detail = reverse("hiring:application_detail", args=[application.pk])

    content = app_client.get(detail).content.decode()
    response = app_client.post(delete_url(application))

    assert "Delete application…" in content
    assert response.status_code == 302
    assert not Application.objects.filter(pk=application.pk).exists()
    assert not StageHistoryEntry.objects.filter(application_id=application.pk).exists()


def test_panel_offers_delete_only_for_a_never_moved_application(app_client, employee):
    never_moved = record(employee)
    moved = moved_back_to_applied(employee, email="sam.lee@example.com")
    detail = reverse("hiring:application_detail", args=[never_moved.pk])

    content = app_client.get(f"{detail}?jobs=all&tab=all").content.decode()
    moved_content = app_client.get(
        reverse("hiring:application_detail", args=[moved.pk])
    ).content.decode()

    job_url = reverse("hiring:pipeline_job", args=[never_moved.job.pk])
    expected = delete_url(never_moved, next=f"{job_url}?jobs=all&tab=all")
    assert f'href="{escape(expected)}"' in content
    assert "Delete application" not in moved_content


# Django admin deletion paths


def admin_bulk_delete(client, model_name, *objects):
    return client.post(
        reverse(f"admin:hiring_{model_name}_changelist"),
        {
            "action": "delete_selected",
            "_selected_action": [obj.pk for obj in objects],
            "post": "yes",
        },
    )


def test_admin_single_delete_of_a_moved_application_is_refused(
    admin_client_logged_in, employee
):
    application = moved_back_to_applied(employee)
    url = reverse("admin:hiring_application_delete", args=[application.pk])
    before = snapshot()

    page = admin_client_logged_in.get(url)
    response = admin_client_logged_in.post(url, {"post": "yes"})

    for refused in (page, response):
        assert refused.status_code == 200
        content = refused.content.decode()
        assert "would require deleting the following protected related objects" in (
            content
        )
        assert "Stage history entry:" in content
    assert snapshot() == before


def test_admin_bulk_delete_of_never_moved_applications_works(
    admin_client_logged_in, employee
):
    first = record(employee)
    second = record(employee, email="sam.lee@example.com")

    response = admin_bulk_delete(admin_client_logged_in, "application", first, second)

    assert response.status_code == 302
    assert not Application.objects.exists()
    assert not StageHistoryEntry.objects.exists()


def test_admin_bulk_delete_including_a_moved_application_is_refused(
    admin_client_logged_in, employee
):
    never_moved = record(employee)
    moved = moved_back_to_applied(employee, email="sam.lee@example.com")
    before = snapshot()

    response = admin_bulk_delete(
        admin_client_logged_in, "application", never_moved, moved
    )

    assert response.status_code == 200
    content = response.content.decode()
    assert "would require deleting the following protected related objects" in content
    assert snapshot() == before


@pytest.mark.parametrize("owner", ["candidate", "job"])
def test_admin_single_and_bulk_delete_of_a_candidate_or_job_with_applications_is_refused(
    admin_client_logged_in, employee, owner
):
    # Even a never-moved application protects its candidate and job.
    application = record(employee)
    obj = application.candidate if owner == "candidate" else application.job
    model_name = "candidate" if owner == "candidate" else "jobopening"
    url = reverse(f"admin:hiring_{model_name}_delete", args=[obj.pk])
    before = snapshot()

    single = admin_client_logged_in.post(url, {"post": "yes"})
    bulk = admin_bulk_delete(admin_client_logged_in, model_name, obj)

    for refused in (single, bulk):
        assert refused.status_code == 200
        content = refused.content.decode()
        assert "would require deleting the following protected related objects" in (
            content
        )
        assert "Application:" in content
    assert type(obj).objects.filter(pk=obj.pk).exists()
    assert snapshot() == before


# Django admin keeps the stage, candidate, job and history read-only.


def admin_change_url(application):
    return reverse("admin:hiring_application_change", args=[application.pk])


def test_admin_application_page_shows_stage_candidate_job_and_history_read_only(
    admin_client_logged_in, employee
):
    application = moved_back_to_applied(employee)

    response = admin_client_logged_in.get(admin_change_url(application))

    assert response.status_code == 200
    form = response.context["adminform"].form
    assert set(form.fields) == {"applied_on", "notes"}
    content = response.content.decode()
    assert "Jane Doe" in content
    assert "Backend Developer" in content
    assert "Applied → Screening" in content
    assert "Screening → Applied" in content


def test_admin_forged_post_cannot_change_stage_candidate_or_job(
    admin_client_logged_in, employee
):
    application = record(employee)
    other_candidate = make_candidate(email="other@example.com")
    other_job = make_job(title="Other")
    entries_before = snapshot()[1]

    response = admin_client_logged_in.post(
        admin_change_url(application),
        {
            "applied_on": timezone.localdate().isoformat(),
            "notes": "Edited in admin.",
            "candidate": other_candidate.pk,
            "job": other_job.pk,
            "stage": Stage.HIRED,
            "_save": "Save",
        },
    )

    assert response.status_code == 302
    stored = Application.objects.get(pk=application.pk)
    assert stored.notes == "Edited in admin."
    assert (stored.candidate_id, stored.job_id, stored.stage) == (
        application.candidate_id,
        application.job_id,
        Stage.APPLIED,
    )
    assert snapshot()[1] == entries_before


def test_admin_refuses_a_future_applied_on_date(admin_client_logged_in, employee):
    application = record(employee)
    tomorrow = timezone.localdate() + timedelta(days=1)

    response = admin_client_logged_in.post(
        admin_change_url(application),
        {"applied_on": tomorrow.isoformat(), "notes": "", "_save": "Save"},
    )

    assert response.status_code == 200
    assert response.context["adminform"].form.errors["applied_on"] == [
        "The applied-on date can't be in the future."
    ]
    application.refresh_from_db()
    assert application.applied_on == timezone.localdate()


def test_admin_cannot_add_an_application(admin_client_logged_in, employee):
    candidate = make_candidate()
    job = make_job()
    url = reverse("admin:hiring_application_add")

    page = admin_client_logged_in.get(url)
    response = admin_client_logged_in.post(
        url,
        {
            "candidate": candidate.pk,
            "job": job.pk,
            "applied_on": timezone.localdate().isoformat(),
            "stage": Stage.APPLIED,
        },
    )

    assert page.status_code == 403
    assert response.status_code == 403
    assert not Application.objects.exists()


def test_admin_lists_history_entries_for_viewing(admin_client_logged_in, employee):
    application = moved_back_to_applied(employee)
    entry = application.history.last()

    changelist = admin_client_logged_in.get(
        reverse("admin:hiring_stagehistoryentry_changelist")
    )
    detail = admin_client_logged_in.get(
        reverse("admin:hiring_stagehistoryentry_change", args=[entry.pk])
    )

    assert changelist.status_code == 200
    assert "delete_selected" not in changelist.content.decode()
    assert detail.status_code == 200
    assert not detail.context["has_change_permission"]
    assert not detail.context["has_delete_permission"]


def test_admin_forged_requests_cannot_add_edit_or_delete_history(
    admin_client_logged_in, employee
):
    application = moved_back_to_applied(employee)
    entry = application.history.last()
    change_url = reverse("admin:hiring_stagehistoryentry_change", args=[entry.pk])
    delete_url_ = reverse("admin:hiring_stagehistoryentry_delete", args=[entry.pk])
    forged_entry = {
        "application": application.pk,
        "old_stage": Stage.APPLIED,
        "new_stage": Stage.HIRED,
        "changed_at_0": "2026-01-01",
        "changed_at_1": "09:00:00",
        "changed_by": employee.pk,
        "reason": "Forged.",
    }
    before = snapshot()

    add = admin_client_logged_in.post(
        reverse("admin:hiring_stagehistoryentry_add"), forged_entry
    )
    edit = admin_client_logged_in.post(change_url, forged_entry | {"_save": "Save"})
    delete_page = admin_client_logged_in.get(delete_url_)
    delete = admin_client_logged_in.post(delete_url_, {"post": "yes"})
    bulk = admin_bulk_delete(admin_client_logged_in, "stagehistoryentry", entry)

    assert [r.status_code for r in (add, edit, delete_page, delete)] == [403] * 4
    # Admin has no delete action for history, so it ignores the forged one.
    assert bulk.status_code in (200, 302)
    assert snapshot() == before
