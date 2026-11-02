from io import StringIO

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from hiring import services
from hiring.management.commands.seed_demo import DEMO_PASSWORD
from hiring.models import (
    Application,
    Candidate,
    JobOpening,
    Skill,
    StageHistoryEntry,
)
from hiring.stages import Stage, check_move

from .helpers import assert_stage_matches_history, make_candidate, make_job


def make_application():
    services.create_application(
        candidate=make_candidate(),
        job=make_job(),
        applied_on=timezone.localdate(),
        changed_by=User.objects.create_user(username="recorder", password="pw"),
    )


USER_FIELDS = [f.attname for f in User._meta.concrete_fields if f.name != "password"]


def snapshot():
    """Every field value of the six models, with user passwords kept apart
    so a failing comparison never prints them."""
    models = (Skill, JobOpening, Candidate, Application, StageHistoryEntry)
    records = {m.__name__: list(m.objects.order_by("pk").values()) for m in models}
    users = User.objects.order_by("pk")
    records["User"] = list(users.values(*USER_FIELDS))
    passwords = list(users.values_list("password", flat=True))
    return records, passwords


def assert_unchanged(before):
    records, passwords = snapshot()
    assert records == before[0]
    passwords_unchanged = passwords == before[1]
    assert passwords_unchanged, "user passwords changed"


@pytest.mark.parametrize(
    "make_existing",
    [
        lambda: Skill.objects.create(name="Python"),
        make_job,
        make_candidate,
        make_application,
    ],
    ids=["skill", "job", "candidate", "application"],
)
def test_seed_demo_refuses_when_hiring_data_exists(db, make_existing):
    make_existing()
    before = snapshot()

    with pytest.raises(CommandError, match="hiring data"):
        call_command("seed_demo")

    assert_unchanged(before)


def test_seed_demo_refuses_when_a_demo_username_exists(db):
    User.objects.create_user(username="sam.demo", password="pw")
    before = snapshot()

    with pytest.raises(CommandError, match="sam.demo"):
        call_command("seed_demo")

    assert_unchanged(before)


def test_seed_demo_failure_rolls_back_everything(db, monkeypatch):
    # Closing jobs comes last, after users, records and moves exist.
    def fail(job):
        raise RuntimeError("boom")

    monkeypatch.setattr(services, "close_job", fail)
    before = snapshot()
    out = StringIO()

    with pytest.raises(RuntimeError, match="boom"):
        call_command("seed_demo", stdout=out)

    assert_unchanged(before)
    assert not User.objects.exists()
    assert DEMO_PASSWORD not in out.getvalue()


def seeded_application(name, job_title):
    first, last = name.split()
    return Application.objects.get(
        candidate__first_name=first, candidate__last_name=last, job__title=job_title
    )


def rule_facts(application):
    return services.stage_facts(application.stage, list(application.history.all()))


def can_move(application, target):
    return check_move(
        application.stage,
        target,
        job_open=application.job.status == JobOpening.Status.OPEN,
        **rule_facts(application)._asdict(),
    ).allowed


@pytest.fixture
def seeded(db):
    out = StringIO()
    call_command("seed_demo", stdout=out)
    return out.getvalue()


def test_seed_demo_prints_credentials_with_a_development_warning(seeded):
    assert "DEVELOPMENT ONLY" in seeded
    assert DEMO_PASSWORD in seeded
    for username in ("alex.demo", "sam.demo"):
        assert username in seeded


def test_seed_demo_employees_are_active_non_admin_accounts(seeded):
    users = User.objects.all()
    assert users.count() == 2
    for user in users:
        assert user.is_active
        assert not user.is_staff
        assert not user.is_superuser
        assert user.check_password(DEMO_PASSWORD)


def test_seed_demo_history_matches_stages_and_comes_from_demo_employees(seeded):
    assert_stage_matches_history()
    demo_users = set(User.objects.values_list("pk", flat=True))
    for application in Application.objects.all():
        history = list(application.history.all())
        assert history[0].old_stage == ""
        assert history[0].new_stage == Stage.APPLIED
        assert {entry.changed_by_id for entry in history} <= demo_users


def test_seed_demo_applied_on_dates_are_in_the_past(seeded):
    today = timezone.localdate()
    assert all(a.applied_on < today for a in Application.objects.all())


def test_seed_demo_has_open_and_closed_jobs_with_skills(seeded):
    assert JobOpening.objects.filter(status=JobOpening.Status.OPEN).exists()
    closed = JobOpening.objects.filter(status=JobOpening.Status.CLOSED)
    assert closed.exists()
    assert all(job.closed_at for job in closed)
    assert all(job.skills.exists() for job in JobOpening.objects.all())


def test_seed_demo_application_reopened_from_withdrawn_cant_skip(seeded):
    maya = seeded_application("Maya Chen", "Backend Developer")
    assert maya.stage == Stage.SCREENING
    assert rule_facts(maya).reopened_from_withdrawn
    assert can_move(maya, Stage.INTERVIEW)
    assert not can_move(maya, Stage.FINAL_REVIEW)


def test_seed_demo_restricted_application_reopened_from_hired_stays_restricted(
    seeded,
):
    aisha = seeded_application("Aisha Bello", "Product Designer")
    assert aisha.stage == Stage.OFFER
    assert aisha.history.filter(new_stage=Stage.HIRED).exists()
    assert rule_facts(aisha).reopened_from_withdrawn
    assert can_move(aisha, Stage.HIRED)


@pytest.mark.parametrize(
    ("name", "job_title", "stage", "reopen_to"),
    [
        ("Jordan Rivera", "Backend Developer", Stage.HIRED, Stage.FINAL_REVIEW),
        ("Priya Patel", "Backend Developer", Stage.REJECTED, Stage.SCREENING),
    ],
)
def test_seed_demo_hired_and_rejected_applications_are_reopenable(
    seeded, name, job_title, stage, reopen_to
):
    application = seeded_application(name, job_title)
    assert application.stage == stage
    assert not rule_facts(application).reopened_from_withdrawn
    assert can_move(application, reopen_to)


def test_seed_demo_rejection_reason_is_on_its_history_entry(seeded):
    priya = seeded_application("Priya Patel", "Backend Developer")
    assert priya.history.last().reason


def test_seed_demo_closed_job_has_in_progress_applications(seeded):
    job = JobOpening.objects.with_in_progress_count().get(
        status=JobOpening.Status.CLOSED
    )
    assert job.in_progress_count >= 2
    lena = seeded_application("Lena Fischer", job.title)
    assert can_move(lena, Stage.REJECTED)
    assert not can_move(lena, Stage.FINAL_REVIEW)


def test_seed_demo_candidates_with_several_applications(seeded):
    assert seeded_application("Maya Chen", "Product Designer")
    several = [c for c in Candidate.objects.all() if c.applications.count() >= 2]
    assert len(several) >= 2


def test_seed_demo_includes_a_deletable_never_moved_application(seeded):
    sam = seeded_application("Sam Okafor", "Backend Developer")
    assert not Application.objects.filter(pk=sam.pk).moved().exists()
    leo = seeded_application("Leo Martins", "Backend Developer")
    assert leo.stage == Stage.APPLIED
    assert Application.objects.filter(pk=leo.pk).moved().exists()


def test_seed_demo_twice_refuses_the_second_run(seeded):
    before = snapshot()

    with pytest.raises(CommandError, match="hiring data"):
        call_command("seed_demo")

    assert_unchanged(before)
