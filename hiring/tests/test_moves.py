import html
import re

import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import DatabaseError
from django.urls import reverse
from django.utils import timezone

from hiring import services
from hiring.models import Application, JobOpening, StageHistoryEntry
from hiring.stages import ACTIVE_STAGES, Stage
from hiring.tests.helpers import assert_stage_matches_history, make_candidate, make_job


@pytest.fixture
def recorder(db):
    return User.objects.create_user(username="recorder", password="pw")


@pytest.fixture
def mover(db):
    return User.objects.create_user(username="mover", password="pw")


@pytest.fixture
def application(recorder):
    return services.create_application(
        candidate=make_candidate(),
        job=make_job(),
        applied_on=timezone.localdate(),
        changed_by=recorder,
    )


def test_successful_move_updates_the_stage_and_writes_one_history_entry(
    application, mover
):
    before = timezone.now()

    services.move_application(application, Stage.INTERVIEW, changed_by=mover)

    assert Application.objects.get(pk=application.pk).stage == Stage.INTERVIEW
    entries = list(application.history.all())
    assert len(entries) == 2  # the initial Applied entry plus this move
    entry = entries[-1]
    assert entry.old_stage == Stage.APPLIED
    assert entry.new_stage == Stage.INTERVIEW
    assert entry.changed_by == mover
    assert before <= entry.changed_at <= timezone.now()
    assert entry.reason == ""


def test_stale_move_is_refused_and_changes_nothing(application, mover):
    # One tab loaded the application at Applied; another tab then rejected it.
    stale = Application.objects.get(pk=application.pk)
    services.move_application(application, Stage.REJECTED, changed_by=mover)
    history_before = list(application.history.values_list("pk", "new_stage"))
    assert stale.stage == Stage.APPLIED  # the first tab still shows Applied

    # Applied -> Screening would be allowed, but the saved stage is Rejected.
    with pytest.raises(ValidationError) as caught:
        services.move_application(stale, Stage.SCREENING, changed_by=mover)

    assert caught.value.messages == [
        "A Rejected application reopens only to Applied, "
        "the stage it was in before that outcome."
    ]
    assert Application.objects.get(pk=application.pk).stage == Stage.REJECTED
    assert list(application.history.values_list("pk", "new_stage")) == (history_before)


# Service: allowed and blocked moves

CLOSED_JOB_REASON = (
    "This job is closed, so its applications can only be rejected or marked withdrawn."
)
FINAL_TO_FINAL_REASON = (
    "A finished application can't move straight to another outcome. Reopen it first."
)


def move(application, target, mover, reason=""):
    return services.move_application(
        application, target, changed_by=mover, reason=reason
    )


def history(application):
    return list(application.history.values_list("old_stage", "new_stage", "reason"))


def close(job):
    JobOpening.objects.filter(pk=job.pk).update(
        status=JobOpening.Status.CLOSED, closed_at=timezone.now()
    )


@pytest.mark.parametrize(
    ("start", "target"),
    [
        (Stage.APPLIED, Stage.SCREENING),  # one step forward
        (Stage.SCREENING, Stage.OFFER),  # skip forward
        (Stage.APPLIED, Stage.HIRED),  # skip to Hired
        (Stage.OFFER, Stage.HIRED),  # last step
        (Stage.OFFER, Stage.APPLIED),  # back to any earlier active stage
        (Stage.FINAL_REVIEW, Stage.SCREENING),
    ],
)
def test_open_job_moves_succeed_through_the_service(application, mover, start, target):
    if start != Stage.APPLIED:
        move(application, start, mover)

    move(application, target, mover)

    assert Application.objects.get(pk=application.pk).stage == target
    assert history(application)[-1] == (start, target, "")


@pytest.mark.parametrize("target", [Stage.REJECTED, Stage.WITHDRAWN])
@pytest.mark.parametrize("start", ACTIVE_STAGES)
def test_ending_from_any_active_stage_saves_the_reason(
    application, mover, start, target
):
    if start != Stage.APPLIED:
        move(application, start, mover)

    move(application, target, mover, reason="Accepted another offer.")

    assert Application.objects.get(pk=application.pk).stage == target
    assert history(application)[-1] == (start, target, "Accepted another offer.")


def test_ending_without_a_reason_is_allowed(application, mover):
    move(application, Stage.REJECTED, mover)

    assert history(application)[-1] == (Stage.APPLIED, Stage.REJECTED, "")


@pytest.mark.parametrize("target", [Stage.SCREENING, Stage.HIRED])
def test_a_reason_is_refused_for_other_moves_and_nothing_changes(
    application, mover, target
):
    before = history(application)

    with pytest.raises(ValidationError) as caught:
        move(application, target, mover, reason="Strong referral.")

    assert caught.value.messages == [
        "A reason can only be given when rejecting or withdrawing."
    ]
    assert Application.objects.get(pk=application.pk).stage == Stage.APPLIED
    assert history(application) == before


def test_move_between_final_outcomes_is_blocked_and_changes_nothing(application, mover):
    move(application, Stage.REJECTED, mover)
    before = history(application)

    with pytest.raises(ValidationError) as caught:
        move(application, Stage.WITHDRAWN, mover)

    assert caught.value.messages == [FINAL_TO_FINAL_REASON]
    assert Application.objects.get(pk=application.pk).stage == Stage.REJECTED
    assert history(application) == before


@pytest.mark.parametrize("target", [Stage.REJECTED, Stage.WITHDRAWN])
def test_closed_job_allows_ending_an_active_application(application, mover, target):
    move(application, Stage.INTERVIEW, mover)
    close(application.job)

    move(application, target, mover)

    assert Application.objects.get(pk=application.pk).stage == target


@pytest.mark.parametrize(
    "target", [Stage.HIRED, Stage.OFFER, Stage.FINAL_REVIEW, Stage.APPLIED]
)
def test_closed_job_blocks_other_moves_and_changes_nothing(application, mover, target):
    move(application, Stage.INTERVIEW, mover)
    close(application.job)
    before = history(application)

    with pytest.raises(ValidationError) as caught:
        move(application, target, mover)

    assert caught.value.messages == [CLOSED_JOB_REASON]
    assert Application.objects.get(pk=application.pk).stage == Stage.INTERVIEW
    assert history(application) == before


def test_move_reads_the_job_status_from_the_database(application, mover):
    # The caller's job still says Open, but the job has been closed since.
    close(application.job)
    assert application.job.status == JobOpening.Status.OPEN

    with pytest.raises(ValidationError) as caught:
        move(application, Stage.SCREENING, mover)

    assert caught.value.messages == [CLOSED_JOB_REASON]
    assert Application.objects.get(pk=application.pk).stage == Stage.APPLIED


def test_move_reads_a_reopened_job_from_the_database(application, mover):
    # The caller's job still says Closed, but the job has been reopened since.
    application.job.status = JobOpening.Status.CLOSED

    move(application, Stage.SCREENING, mover)

    assert Application.objects.get(pk=application.pk).stage == Stage.SCREENING


def test_failed_history_write_rolls_back_the_stage(application, mover, monkeypatch):
    def fail(**fields):
        raise DatabaseError("history write failed")

    monkeypatch.setattr(StageHistoryEntry.objects, "create", fail)

    with pytest.raises(DatabaseError):
        move(application, Stage.SCREENING, mover)

    assert Application.objects.get(pk=application.pk).stage == Stage.APPLIED
    assert application.history.count() == 1


def test_stage_always_equals_the_latest_history_entry(application, mover):
    other = services.create_application(
        candidate=make_candidate(email="other@example.com"),
        job=application.job,
        applied_on=timezone.localdate(),
        changed_by=mover,
    )
    assert_stage_matches_history()

    steps = [
        (application, Stage.INTERVIEW),
        (other, Stage.SCREENING),
        (application, Stage.SCREENING),
        (application, Stage.REJECTED),
        (application, Stage.HIRED),  # refused: final to final
        (other, Stage.WITHDRAWN),
    ]
    for target_application, target in steps:
        try:
            move(target_application, target, mover)
        except ValidationError:
            pass
        assert_stage_matches_history()

    assert Application.objects.get(pk=application.pk).stage == Stage.REJECTED
    assert len(history(application)) == 4  # the refused move wrote nothing


# Facts derived from history across reopen and withdraw sequences


def no_skip_reason(step):
    return (
        "This application was reopened after being withdrawn, so it can't skip "
        f"stages. It can only move forward to {step.label}."
    )


def test_history_facts_stay_correct_through_repeated_reopen_and_withdraw(
    application, mover
):
    def expect(stage, before, restricted):
        current = Application.objects.get(pk=application.pk)
        assert current.stage == stage
        facts = services.stage_facts(current.stage, list(current.history.all()))
        assert facts._asdict() == {
            "stage_before_outcome": before,
            "reopened_from_withdrawn": restricted,
        }
        assert_stage_matches_history()

    def refused_skip(target, step):
        before = history(application)
        with pytest.raises(ValidationError) as caught:
            move(application, target, mover)
        assert caught.value.messages == [no_skip_reason(step)]
        assert history(application) == before

    expect(Stage.APPLIED, None, False)
    move(application, Stage.INTERVIEW, mover)  # unrestricted, so a skip is fine
    expect(Stage.INTERVIEW, None, False)
    move(application, Stage.WITHDRAWN, mover)
    expect(Stage.WITHDRAWN, None, False)

    move(application, Stage.APPLIED, mover)  # reopen from Withdrawn
    expect(Stage.APPLIED, None, True)
    refused_skip(Stage.INTERVIEW, step=Stage.SCREENING)
    move(application, Stage.SCREENING, mover)
    expect(Stage.SCREENING, None, True)

    move(application, Stage.REJECTED, mover)
    expect(Stage.REJECTED, Stage.SCREENING, True)
    move(application, Stage.SCREENING, mover)  # reopen from Rejected
    expect(Stage.SCREENING, None, True)
    refused_skip(Stage.FINAL_REVIEW, step=Stage.INTERVIEW)

    move(application, Stage.WITHDRAWN, mover)
    expect(Stage.WITHDRAWN, None, True)
    move(application, Stage.APPLIED, mover)  # reopen from Withdrawn again
    expect(Stage.APPLIED, None, True)
    refused_skip(Stage.INTERVIEW, step=Stage.SCREENING)

    # One application record throughout: the initial entry plus eight moves.
    assert Application.objects.count() == 1
    assert len(history(application)) == 9


# The move view


def move_url(application, jobs=None):
    url = reverse("hiring:application_move", args=[application.pk])
    return f"{url}?jobs={jobs}" if jobs else url


def detail_url(application):
    return reverse("hiring:application_detail", args=[application.pk])


def page_text(response):
    return html.unescape(response.content.decode())


@pytest.fixture
def employee(employee_client):
    return User.objects.get(username="employee")


def test_move_view_redirects_to_the_workspace_keeping_the_sidebar_filter(
    employee_client, employee, application
):
    response = employee_client.post(
        move_url(application, jobs="all"), {"stage": Stage.SCREENING}
    )

    assert response.status_code == 302
    assert response.url == detail_url(application) + "?jobs=all"
    entry = application.history.last()
    assert (entry.old_stage, entry.new_stage) == (Stage.APPLIED, Stage.SCREENING)
    assert entry.changed_by == employee


@pytest.mark.parametrize("jobs", [None, "bogus"])
def test_move_view_drops_a_missing_or_unknown_sidebar_filter(
    employee_client, application, jobs
):
    response = employee_client.post(
        move_url(application, jobs=jobs), {"stage": Stage.SCREENING}
    )

    assert response.url == detail_url(application)


def test_move_view_saves_the_reason_and_the_timeline_shows_it(
    employee_client, application
):
    response = employee_client.post(
        move_url(application, jobs="open"),
        {"stage": Stage.REJECTED, "reason": "  Not enough experience.  "},
        follow=True,
    )

    assert application.history.last().reason == "Not enough experience."
    assert "Reason: Not enough experience." in page_text(response)


def test_move_view_treats_a_blank_reason_as_none(employee_client, application):
    employee_client.post(
        move_url(application), {"stage": Stage.SCREENING, "reason": "   "}
    )

    assert Application.objects.get(pk=application.pk).stage == Stage.SCREENING


def test_stale_move_view_shows_the_error_and_refreshed_actions(
    employee_client, application, mover
):
    # Another tab rejected the application after this page loaded.
    move(application, Stage.REJECTED, mover)
    before = history(application)

    response = employee_client.post(
        move_url(application, jobs="open"), {"stage": Stage.SCREENING}
    )

    assert response.status_code == 200
    page = page_text(response)
    assert "That move wasn't made." in page
    assert (
        "A Rejected application reopens only to Applied, "
        "the stage it was in before that outcome." in page
    )
    # The actions now match Rejected: only the reopen remains.
    assert stage_buttons(page) == ["applied"]
    assert "Reopen to Applied" in page
    assert Application.objects.get(pk=application.pk).stage == Stage.REJECTED
    assert history(application) == before


def test_move_view_refuses_an_unknown_stage(employee_client, application):
    response = employee_client.post(move_url(application), {"stage": "bogus"})

    assert response.status_code == 200
    assert "That move wasn't made." in page_text(response)
    assert history(application) == [("", Stage.APPLIED, "")]


def test_move_view_requires_post(employee_client, application):
    response = employee_client.get(move_url(application))

    assert response.status_code == 405


# The detail panel's actions


def stage_buttons(page):
    """Target stages posted by the panel's move forms, in page order."""
    return re.findall(r'<input type="hidden" name="stage" value="(\w+)">', page)


def without_confirmation_boxes(page):
    return re.sub(r"<details[^>]*data-confirm=.*?</details>", "", page, flags=re.S)


def blocked_moves(page):
    section = re.search(r'<ul[^>]*aria-label="Blocked moves">(.*?)</ul>', page, re.S)
    if section is None:
        return []
    items = re.findall(r"<li[^>]*>(.*?)</li>", section.group(1), re.S)
    return [" ".join(re.sub(r"<[^>]+>", " ", item).split()) for item in items]


def test_panel_on_an_open_job_offers_advance_confirmations_and_other_moves(
    employee_client, application
):
    page = page_text(employee_client.get(detail_url(application)))

    assert "Advance to Screening" in page
    assert stage_buttons(page) == [
        "screening",  # advance
        "rejected",
        "withdrawn",
        "interview",  # other moves, in pipeline order
        "final_review",
        "offer",
        "hired",
    ]
    assert "Reject…" in page
    assert "Mark withdrawn…" in page
    # Rejected and Withdrawn are reachable only inside their confirmation box.
    outside = stage_buttons(without_confirmation_boxes(page))
    assert "rejected" not in outside
    assert "withdrawn" not in outside
    assert blocked_moves(page) == []
    assert "This job is closed." not in page


def test_panel_on_a_closed_job_shows_the_alert_and_only_ending_moves(
    employee_client, application, mover
):
    move(application, Stage.INTERVIEW, mover)
    close(application.job)

    page = page_text(employee_client.get(detail_url(application)))

    assert "This job is closed. Its applications keep their stages" in page
    assert stage_buttons(page) == ["rejected", "withdrawn"]
    assert "Advance to" not in page
    assert blocked_moves(page) == [
        f"{label}: {CLOSED_JOB_REASON}"
        for label in ["Applied", "Screening", "Final Review", "Offer", "Hired"]
    ]


def test_panel_for_a_finished_application_explains_every_blocked_move(
    employee_client, application, mover
):
    move(application, Stage.REJECTED, mover)

    page = page_text(employee_client.get(detail_url(application)))

    assert stage_buttons(page) == ["applied"]
    assert "Reopen to Applied" in page
    wrong = (
        "A Rejected application reopens only to Applied, "
        "the stage it was in before that outcome."
    )
    assert blocked_moves(page) == [
        *(
            f"{label}: {wrong}"
            for label in ["Screening", "Interview", "Final Review", "Offer"]
        ),
        f"Hired: {FINAL_TO_FINAL_REASON}",
        f"Withdrawn: {FINAL_TO_FINAL_REASON}",
    ]


def test_panel_move_forms_keep_the_sidebar_filter(employee_client, application):
    page = page_text(employee_client.get(detail_url(application) + "?jobs=all"))

    actions = re.findall(r'<form method="post" action="([^"]+)"', page)
    moves = [action for action in actions if "/move/" in action]
    assert moves
    assert set(moves) == {move_url(application, jobs="all")}


# Reopening finished applications

REOPEN_CLOSED_JOB_REASON = (
    "This job is closed. Reopen the job before reopening this application."
)


def walk(application, mover, *targets):
    for target in targets:
        move(application, target, mover)


def facts(application):
    current = Application.objects.get(pk=application.pk)
    return services.stage_facts(current.stage, list(current.history.all()))


@pytest.mark.parametrize("outcome", [Stage.HIRED, Stage.REJECTED])
def test_hired_or_rejected_reopens_to_the_previous_stage_and_may_skip_afterward(
    application, mover, outcome
):
    walk(application, mover, Stage.SCREENING, outcome)

    move(application, Stage.SCREENING, mover)

    assert Application.objects.get(pk=application.pk).stage == Stage.SCREENING
    assert history(application)[-1] == (outcome, Stage.SCREENING, "")
    assert not facts(application).reopened_from_withdrawn
    move(application, Stage.OFFER, mover)  # never withdrawn, so skipping is fine
    assert Application.objects.get(pk=application.pk).stage == Stage.OFFER


@pytest.mark.parametrize("start", ACTIVE_STAGES)
def test_reopening_withdrawn_returns_the_same_application_to_applied(
    application, mover, start
):
    if start != Stage.APPLIED:
        move(application, start, mover)
    move(application, Stage.WITHDRAWN, mover)

    move(application, Stage.APPLIED, mover)

    assert Application.objects.count() == 1
    reopened = Application.objects.get()
    assert reopened.pk == application.pk
    assert reopened.stage == Stage.APPLIED
    assert history(application)[-1] == (Stage.WITHDRAWN, Stage.APPLIED, "")
    assert_stage_matches_history()


def test_restricted_application_stays_restricted_after_rejected_reopen(
    application, mover
):
    walk(application, mover, Stage.WITHDRAWN, Stage.APPLIED, Stage.SCREENING)
    walk(application, mover, Stage.REJECTED, Stage.SCREENING)  # reject, reopen
    before = history(application)

    with pytest.raises(ValidationError) as caught:
        move(application, Stage.OFFER, mover)

    assert caught.value.messages == [no_skip_reason(Stage.INTERVIEW)]
    assert history(application) == before
    assert facts(application).reopened_from_withdrawn


def test_restricted_application_stays_restricted_after_hired_reopen_to_offer(
    application, mover
):
    walk(application, mover, Stage.WITHDRAWN, Stage.APPLIED)
    # One step at a time, including Offer -> Hired.
    walk(
        application,
        mover,
        Stage.SCREENING,
        Stage.INTERVIEW,
        Stage.FINAL_REVIEW,
        Stage.OFFER,
        Stage.HIRED,
    )
    move(application, Stage.OFFER, mover)  # reopen to the stage before Hired
    assert Application.objects.get(pk=application.pk).stage == Stage.OFFER
    move(application, Stage.SCREENING, mover)  # backward moves stay allowed
    before = history(application)

    with pytest.raises(ValidationError) as caught:
        move(application, Stage.FINAL_REVIEW, mover)

    assert caught.value.messages == [no_skip_reason(Stage.INTERVIEW)]
    assert history(application) == before


@pytest.mark.parametrize(
    ("path", "reopen_to"),
    [
        ((Stage.OFFER, Stage.HIRED), Stage.OFFER),
        ((Stage.INTERVIEW, Stage.REJECTED), Stage.INTERVIEW),
        ((Stage.INTERVIEW, Stage.WITHDRAWN), Stage.APPLIED),
    ],
    ids=["Hired", "Rejected", "Withdrawn"],
)
def test_reopening_on_a_closed_job_is_blocked_and_changes_nothing(
    application, mover, path, reopen_to
):
    walk(application, mover, *path)
    close(application.job)
    before = history(application)

    with pytest.raises(ValidationError) as caught:
        move(application, reopen_to, mover)

    assert caught.value.messages == [REOPEN_CLOSED_JOB_REASON]
    assert Application.objects.get(pk=application.pk).stage == path[-1]
    assert history(application) == before


def test_reopen_without_previous_stage_history_is_blocked(application, mover):
    # Rejected with no history entry recording the move into it.
    Application.objects.filter(pk=application.pk).update(stage=Stage.REJECTED)
    before = history(application)

    with pytest.raises(ValidationError) as caught:
        move(application, Stage.APPLIED, mover)

    assert caught.value.messages == [
        "The stage history doesn't show which stage came before Rejected, "
        "so this application can't be reopened."
    ]
    assert Application.objects.get(pk=application.pk).stage == Stage.REJECTED
    assert history(application) == before


def test_reopen_through_the_move_view_records_it_and_returns_to_the_workspace(
    employee_client, employee, application, mover
):
    walk(application, mover, Stage.INTERVIEW, Stage.REJECTED)

    response = employee_client.post(
        move_url(application, jobs="all"), {"stage": Stage.INTERVIEW}
    )

    assert response.url == detail_url(application) + "?jobs=all"
    assert Application.objects.get(pk=application.pk).stage == Stage.INTERVIEW
    entry = application.history.last()
    assert (entry.old_stage, entry.new_stage) == (Stage.REJECTED, Stage.INTERVIEW)
    assert entry.changed_by == employee


def test_withdrawn_reopen_through_the_move_view_keeps_the_same_application(
    employee_client, application, mover
):
    move(application, Stage.WITHDRAWN, mover)

    employee_client.post(move_url(application), {"stage": Stage.APPLIED})

    assert Application.objects.count() == 1
    assert Application.objects.get(pk=application.pk).stage == Stage.APPLIED


# The panel for finished and restricted applications

NO_SKIP_ALERT = "This application was reopened after being withdrawn"


def test_panel_offers_reopen_to_applied_for_a_withdrawn_application(
    employee_client, application, mover
):
    walk(application, mover, Stage.INTERVIEW, Stage.WITHDRAWN)

    page = page_text(employee_client.get(detail_url(application)))

    assert stage_buttons(page) == ["applied"]
    assert "Reopen to Applied" in page
    assert "Advance to" not in page
    assert NO_SKIP_ALERT not in page  # not reopened yet


def test_panel_on_a_closed_job_explains_why_reopen_is_blocked(
    employee_client, application, mover
):
    walk(application, mover, Stage.INTERVIEW, Stage.REJECTED)
    close(application.job)

    page = page_text(employee_client.get(detail_url(application)))

    assert stage_buttons(page) == []
    assert "Reopen to" not in page
    assert f"Interview: {REOPEN_CLOSED_JOB_REASON}" in blocked_moves(page)


def test_panel_for_a_restricted_application_shows_the_alert_and_single_steps(
    employee_client, application, mover
):
    walk(application, mover, Stage.WITHDRAWN, Stage.APPLIED, Stage.SCREENING)
    walk(application, mover, Stage.INTERVIEW)

    page = page_text(employee_client.get(detail_url(application)))

    assert NO_SKIP_ALERT in page
    assert "Advance to Final Review" in page
    assert stage_buttons(page) == [
        "final_review",  # advance, the only forward move
        "rejected",
        "withdrawn",
        "applied",  # backward moves stay allowed
        "screening",
    ]
    reason = no_skip_reason(Stage.FINAL_REVIEW)
    assert blocked_moves(page) == [f"Offer: {reason}", f"Hired: {reason}"]


def test_panel_keeps_the_alert_after_a_later_outcome(
    employee_client, application, mover
):
    walk(application, mover, Stage.WITHDRAWN, Stage.APPLIED, Stage.REJECTED)

    page = page_text(employee_client.get(detail_url(application)))

    assert NO_SKIP_ALERT in page
    assert "Reopen to Applied" in page


def test_panel_for_an_unrestricted_application_has_no_alert(
    employee_client, application
):
    page = page_text(employee_client.get(detail_url(application)))

    assert NO_SKIP_ALERT not in page


# Reopening a job


def test_reopening_a_job_reenables_active_and_leaves_finished_applications(
    application, mover
):
    job = application.job
    others = {
        stage: services.create_application(
            candidate=make_candidate(email=f"{stage}@example.com"),
            job=job,
            applied_on=timezone.localdate(),
            changed_by=mover,
        )
        for stage in (Stage.HIRED, Stage.REJECTED, Stage.WITHDRAWN)
    }
    for stage, other in others.items():
        move(other, stage, mover)
    move(application, Stage.INTERVIEW, mover)
    services.close_job(JobOpening.objects.get(pk=job.pk))
    with pytest.raises(ValidationError):
        move(application, Stage.OFFER, mover)
    histories = {stage: history(other) for stage, other in others.items()}

    services.reopen_job(JobOpening.objects.get(pk=job.pk))

    job.refresh_from_db()
    assert job.status == JobOpening.Status.OPEN
    assert job.closed_at is None
    for stage, other in others.items():
        assert Application.objects.get(pk=other.pk).stage == stage
        assert history(other) == histories[stage]
    move(application, Stage.OFFER, mover)  # active applications move again
    assert Application.objects.get(pk=application.pk).stage == Stage.OFFER
