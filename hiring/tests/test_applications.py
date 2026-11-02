from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import DatabaseError, IntegrityError, transaction
from django.db.models import ProtectedError
from django.urls import reverse
from django.utils import timezone

from hiring import services
from hiring.models import Application, Candidate, JobOpening, StageHistoryEntry
from hiring.stages import Stage
from hiring.tests.helpers import make_candidate, make_job

DUPLICATE_ERROR = "This candidate has already applied to this job."
CLOSED_JOB_ERROR = "This job is closed and can't accept new applications."
FUTURE_DATE_ERROR = "The applied-on date can't be in the future."


@pytest.fixture
def employee(db):
    return User.objects.create_user(username="recorder", password="pw")


def test_new_application_starts_at_applied_with_one_initial_history_entry(employee):
    candidate = make_candidate()
    job = make_job()
    before = timezone.now()

    returned = services.create_application(
        candidate=candidate,
        job=job,
        applied_on=timezone.localdate(),
        changed_by=employee,
    )

    applications = list(Application.objects.all())
    assert len(applications) == 1
    application = applications[0]
    assert returned == application
    assert application.candidate == candidate
    assert application.job == job
    assert application.stage == Stage.APPLIED

    entries = list(application.history.all())
    assert len(entries) == 1
    entry = entries[0]
    assert entry.old_stage == ""
    assert entry.new_stage == Stage.APPLIED
    assert entry.changed_by == employee
    assert before <= entry.changed_at <= timezone.now()


def test_duplicate_application_shows_form_error_even_when_existing_is_rejected(
    client, employee
):
    client.force_login(employee)
    candidate = make_candidate()
    job = make_job()
    existing = services.create_application(
        candidate=candidate,
        job=job,
        applied_on=timezone.localdate(),
        changed_by=employee,
    )
    # Moving applications arrives in Phase 8, so set the stage directly.
    Application.objects.filter(pk=existing.pk).update(stage=Stage.REJECTED)

    # A forged POST: the picker would never offer this job.
    response = client.post(
        reverse("hiring:candidate_application_create", args=[candidate.pk]),
        {"job": job.pk, "applied_on": timezone.localdate().isoformat()},
    )

    assert Application.objects.count() == 1
    assert response.status_code == 200
    assert response.context["form"].errors["job"] == [DUPLICATE_ERROR]
    assert DUPLICATE_ERROR in response.content.decode()
    existing.refresh_from_db()
    assert existing.stage == Stage.REJECTED
    assert existing.history.count() == 1


def create_for(candidate, job, employee):
    return services.create_application(
        candidate=candidate,
        job=job,
        applied_on=timezone.localdate(),
        changed_by=employee,
    )


def test_database_rejects_duplicate_candidate_and_job_when_service_is_bypassed(
    employee,
):
    candidate = make_candidate()
    job = make_job()
    today = timezone.localdate()
    Application.objects.create(
        candidate=candidate, job=job, applied_on=today, stage=Stage.REJECTED
    )

    with pytest.raises(IntegrityError), transaction.atomic():
        Application.objects.create(
            candidate=candidate, job=job, applied_on=today, stage=Stage.APPLIED
        )

    assert Application.objects.count() == 1


def test_failed_history_write_rolls_back_the_application(employee, monkeypatch):
    def fail(**fields):
        raise DatabaseError("history write failed")

    monkeypatch.setattr(StageHistoryEntry.objects, "create", fail)

    with pytest.raises(DatabaseError):
        create_for(make_candidate(), make_job(), employee)

    assert Application.objects.count() == 0


def test_race_recovery_turns_the_unique_constraint_into_the_duplicate_error(
    employee, monkeypatch
):
    # Exercises the race-recovery path by making the pre-check miss an existing
    # application, as a concurrent request could. It doesn't run real
    # concurrent requests.
    candidate = make_candidate()
    job = make_job()
    existing = create_for(candidate, job, employee)
    real_check = services._has_applied
    checks = []

    def miss_first_check(candidate, job):
        checks.append(job)
        return len(checks) > 1 and real_check(candidate, job)

    monkeypatch.setattr(services, "_has_applied", miss_first_check)

    with pytest.raises(ValidationError) as excinfo:
        create_for(candidate, job, employee)

    assert excinfo.value.messages == [DUPLICATE_ERROR]
    assert len(checks) == 2
    assert list(Application.objects.all()) == [existing]
    assert StageHistoryEntry.objects.count() == 1


def test_unrelated_integrity_error_propagates_unchanged(employee, monkeypatch):
    error = IntegrityError("NOT NULL constraint failed: something else")

    def fail(**fields):
        raise error

    monkeypatch.setattr(StageHistoryEntry.objects, "create", fail)

    with pytest.raises(IntegrityError) as excinfo:
        create_for(make_candidate(), make_job(), employee)

    assert excinfo.value is error
    assert Application.objects.count() == 0


def test_closed_job_is_refused_and_writes_nothing(employee):
    candidate = make_candidate()
    # Closing through the service is covered elsewhere; set it directly here.
    job = make_job(status=JobOpening.Status.CLOSED, closed_at=timezone.now())

    with pytest.raises(ValidationError) as excinfo:
        create_for(candidate, job, employee)

    assert excinfo.value.messages == [CLOSED_JOB_ERROR]
    assert Application.objects.count() == 0
    assert StageHistoryEntry.objects.count() == 0


def test_closed_job_check_reads_the_status_from_the_database(employee):
    # A regression test for a stale job object, not a concurrency guarantee.
    candidate = make_candidate()
    job = make_job()
    JobOpening.objects.filter(pk=job.pk).update(status=JobOpening.Status.CLOSED)
    assert job.status == JobOpening.Status.OPEN

    with pytest.raises(ValidationError) as excinfo:
        create_for(candidate, job, employee)

    assert excinfo.value.messages == [CLOSED_JOB_ERROR]
    assert Application.objects.count() == 0


# Recording an application from the candidate page


def add_url(candidate):
    return reverse("hiring:candidate_application_create", args=[candidate.pk])


@pytest.fixture
def logged_in(client, employee):
    client.force_login(employee)
    return client


def test_forged_post_for_a_closed_job_shows_the_error_under_the_job_field(logged_in):
    candidate = make_candidate()
    job = make_job(status=JobOpening.Status.CLOSED, closed_at=timezone.now())

    response = logged_in.post(
        add_url(candidate),
        {"job": job.pk, "applied_on": timezone.localdate().isoformat()},
    )

    assert response.status_code == 200
    assert response.context["form"].errors["job"] == [CLOSED_JOB_ERROR]
    assert "This job is closed and can&#x27;t accept new applications." in (
        response.content.decode()
    )
    assert Application.objects.count() == 0
    assert StageHistoryEntry.objects.count() == 0


def test_picker_lists_only_open_jobs_the_candidate_has_not_applied_to(
    logged_in, employee
):
    candidate = make_candidate()
    applied = make_job(title="Applied Role")
    create_for(candidate, applied, employee)
    make_job(title="Closed Role", status=JobOpening.Status.CLOSED)
    eligible = make_job(title="Eligible Role")
    # Another candidate's application doesn't hide a job.
    other_job = make_job(title="Other Candidate's Role")
    create_for(make_candidate(email="someone@example.com"), other_job, employee)

    response = logged_in.get(add_url(candidate))

    offered = list(response.context["form"].fields["job"].queryset)
    assert offered == [eligible, other_job]
    content = response.content.decode()
    assert "Eligible Role" in content
    assert "Applied Role" not in content
    assert "Closed Role" not in content


def test_applied_on_defaults_to_the_local_date(logged_in):
    response = logged_in.get(add_url(make_candidate()))

    form = response.context["form"]
    assert form["applied_on"].value() == timezone.localdate()


def test_future_applied_on_date_is_rejected(logged_in):
    candidate = make_candidate()
    job = make_job()
    tomorrow = timezone.localdate() + timedelta(days=1)

    response = logged_in.post(
        add_url(candidate), {"job": job.pk, "applied_on": tomorrow.isoformat()}
    )

    assert response.status_code == 200
    assert response.context["form"].errors["applied_on"] == [FUTURE_DATE_ERROR]
    assert Application.objects.count() == 0


def test_model_validation_rejects_a_future_applied_on_date(employee):
    application = Application(
        candidate=make_candidate(),
        job=make_job(),
        applied_on=timezone.localdate() + timedelta(days=1),
        stage=Stage.APPLIED,
    )

    with pytest.raises(ValidationError) as excinfo:
        application.full_clean()

    assert excinfo.value.message_dict["applied_on"] == [FUTURE_DATE_ERROR]


def test_saving_records_the_application_and_opens_its_page(logged_in, employee):
    candidate = make_candidate()
    job = make_job(title="Data Analyst")
    applied_on = timezone.localdate() - timedelta(days=3)

    response = logged_in.post(
        add_url(candidate),
        {"job": job.pk, "applied_on": applied_on.isoformat()},
        follow=True,
    )

    application = Application.objects.get()
    assert response.redirect_chain == [
        (reverse("hiring:application_detail", args=[application.pk]), 302)
    ]
    assert application.candidate == candidate
    assert application.applied_on == applied_on
    assert application.history.get().changed_by == employee
    content = response.content.decode()
    assert "Jane Doe" in content
    assert "Data Analyst" in content
    assert f"{applied_on:%b} {applied_on.day}, {applied_on.year}" in content
    assert "Applied" in content
    assert "recorder" in content


def test_same_candidate_can_apply_to_two_open_jobs(logged_in):
    candidate = make_candidate()
    first = make_job(title="First Role")
    second = make_job(title="Second Role")
    today = timezone.localdate().isoformat()

    logged_in.post(add_url(candidate), {"job": first.pk, "applied_on": today})
    logged_in.post(add_url(candidate), {"job": second.pk, "applied_on": today})

    jobs = {application.job for application in candidate.applications.all()}
    assert jobs == {first, second}
    assert StageHistoryEntry.objects.count() == 2


def test_candidate_detail_lists_applications_with_links(logged_in, employee):
    candidate = make_candidate()
    application = create_for(candidate, make_job(title="Data Analyst"), employee)

    response = logged_in.get(reverse("hiring:candidate_detail", args=[candidate.pk]))

    content = response.content.decode()
    assert f'href="{add_url(candidate)}"' in content
    detail_url = reverse("hiring:application_detail", args=[application.pk])
    assert f'href="{detail_url}?tab=all"' in content
    assert "Data Analyst" in content
    assert "No applications yet." not in content


# Candidate and job are fixed once created.


def test_application_form_ignores_a_submitted_candidate(logged_in):
    candidate = make_candidate()
    other = make_candidate(email="other@example.com")
    job = make_job()

    logged_in.post(
        add_url(candidate),
        {
            "job": job.pk,
            "candidate": other.pk,
            "applied_on": timezone.localdate().isoformat(),
        },
    )

    assert Application.objects.get().candidate == candidate


def test_application_page_offers_no_way_to_change_candidate_or_job(logged_in, employee):
    application = create_for(make_candidate(), make_job(), employee)
    url = reverse("hiring:application_detail", args=[application.pk])
    other_job = make_job(title="Other Role")

    content = logged_in.get(url).content.decode()
    response = logged_in.post(url, {"job": other_job.pk})

    assert 'name="job"' not in content
    assert 'name="candidate"' not in content
    assert response.status_code == 405
    application.refresh_from_db()
    assert application.job != other_job


# Candidates and jobs with applications can't be deleted.


@pytest.fixture
def recorded(employee):
    return create_for(make_candidate(), make_job(), employee)


def test_candidate_with_applications_is_protected_from_model_and_queryset_delete(
    recorded,
):
    candidate = recorded.candidate

    with pytest.raises(ProtectedError):
        candidate.delete()
    with pytest.raises(ProtectedError):
        Candidate.objects.filter(pk=candidate.pk).delete()

    assert Candidate.objects.filter(pk=candidate.pk).exists()


def test_job_with_applications_is_protected_from_model_and_queryset_delete(recorded):
    job = recorded.job

    with pytest.raises(ProtectedError):
        job.delete()
    with pytest.raises(ProtectedError):
        JobOpening.objects.filter(pk=job.pk).delete()

    assert JobOpening.objects.filter(pk=job.pk).exists()


@pytest.mark.parametrize("method", ["get", "post"])
def test_candidate_delete_page_explains_why_it_is_blocked(logged_in, recorded, method):
    url = reverse("hiring:candidate_delete", args=[recorded.candidate.pk])

    response = getattr(logged_in, method)(url)

    assert response.status_code == 200
    content = response.content.decode()
    assert "Can't delete candidate" in content
    assert "Backend Developer" in content
    assert 'btn-error">Delete</button>' not in content
    assert Candidate.objects.filter(pk=recorded.candidate.pk).exists()


@pytest.mark.parametrize("method", ["get", "post"])
def test_job_delete_page_explains_why_it_is_blocked(logged_in, recorded, method):
    url = reverse("hiring:job_delete", args=[recorded.job.pk])

    response = getattr(logged_in, method)(url)

    assert response.status_code == 200
    content = response.content.decode()
    assert "Can't delete job" in content
    assert "Jane Doe" in content
    assert 'btn-error">Delete</button>' not in content
    assert JobOpening.objects.filter(pk=recorded.job.pk).exists()
