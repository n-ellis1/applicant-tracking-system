"""Hiring stages and the rules for moving between them. No database access."""

from typing import NamedTuple

from django.db import models


class Stage(models.TextChoices):
    APPLIED = "applied", "Applied"
    SCREENING = "screening", "Screening"
    INTERVIEW = "interview", "Interview"
    FINAL_REVIEW = "final_review", "Final Review"
    OFFER = "offer", "Offer"
    HIRED = "hired", "Hired"
    REJECTED = "rejected", "Rejected"
    WITHDRAWN = "withdrawn", "Withdrawn"


# Both groups are in pipeline order.
ACTIVE_STAGES = (
    Stage.APPLIED,
    Stage.SCREENING,
    Stage.INTERVIEW,
    Stage.FINAL_REVIEW,
    Stage.OFFER,
)
FINAL_STAGES = (Stage.HIRED, Stage.REJECTED, Stage.WITHDRAWN)


def next_stage(stage):
    """The stage one step forward, or None for a final stage."""
    forward = (*ACTIVE_STAGES, Stage.HIRED)
    if stage not in ACTIVE_STAGES:
        return None
    return forward[forward.index(stage) + 1]


class MoveCheck(NamedTuple):
    allowed: bool
    reason: str = ""


def check_move(
    current,
    target,
    *,
    job_open,
    stage_before_outcome=None,
    reopened_from_withdrawn=False,
):
    """Whether an application may move from current to target, with a reason
    when it may not."""
    current, target = Stage(current), Stage(target)
    if current == target:
        return MoveCheck(False, f"The application is already at {current.label}.")
    if current in FINAL_STAGES:
        if target in FINAL_STAGES:
            return MoveCheck(
                False,
                "A finished application can't move straight to another outcome. "
                "Reopen it first.",
            )
        return _check_reopen(current, target, job_open, stage_before_outcome)
    # A closed job stops progressing but its applications can still end.
    if not job_open and target not in (Stage.REJECTED, Stage.WITHDRAWN):
        return MoveCheck(
            False,
            "This job is closed, so its applications can only be rejected "
            "or marked withdrawn.",
        )
    # Once reopened from Withdrawn, every forward move is a single step.
    step = next_stage(current)
    forward = (*ACTIVE_STAGES, Stage.HIRED)
    if (
        reopened_from_withdrawn
        and target in forward
        and forward.index(target) > forward.index(step)
    ):
        return MoveCheck(
            False,
            "This application was reopened after being withdrawn, so it can't "
            f"skip stages. It can only move forward to {step.label}.",
        )
    # From an active stage, any other stage is allowed.
    return MoveCheck(True)


def _check_reopen(current, target, job_open, stage_before_outcome):
    """Withdrawn reopens to Applied; Hired and Rejected reopen only to the
    active stage before that outcome."""
    if current == Stage.WITHDRAWN:
        if target != Stage.APPLIED:
            return MoveCheck(
                False,
                "A Withdrawn application reopens only to Applied, "
                "so it repeats every stage.",
            )
        return _reopen_on_open_job(job_open)
    if stage_before_outcome not in ACTIVE_STAGES:
        # Never guess a target when history doesn't name one.
        return MoveCheck(
            False,
            "The stage history doesn't show which stage came before "
            f"{current.label}, so this application can't be reopened.",
        )
    before = Stage(stage_before_outcome)
    if target != before:
        return MoveCheck(
            False,
            f"A {current.label} application reopens only to {before.label}, "
            "the stage it was in before that outcome.",
        )
    return _reopen_on_open_job(job_open)


def _reopen_on_open_job(job_open):
    if not job_open:
        return MoveCheck(
            False,
            "This job is closed. Reopen the job before reopening this application.",
        )
    return MoveCheck(True)
