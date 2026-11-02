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
        "This application is finished. Reopen it before moving it."
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
    assert "This application is finished. Reopen it before moving it." in page
    # The actions now match Rejected: nothing to advance, reject or withdraw.
    assert stage_buttons(page) == []
    assert "No stage moves are available." in page
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

    assert stage_buttons(page) == []
    assert "No stage moves are available." in page
    reopen = "This application is finished. Reopen it before moving it."
    assert blocked_moves(page) == [
        *(
            f"{label}: {reopen}"
            for label in ["Applied", "Screening", "Interview", "Final Review", "Offer"]
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
