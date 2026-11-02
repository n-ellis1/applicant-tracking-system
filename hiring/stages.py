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


def check_move(current, target, *, job_open):
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
        # Reopening a finished application comes with its own rules (Phase 9).
        return MoveCheck(
            False, "This application is finished. Reopen it before moving it."
        )
    # A closed job stops progressing but its applications can still end.
    if not job_open and target not in (Stage.REJECTED, Stage.WITHDRAWN):
        return MoveCheck(
            False,
            "This job is closed, so its applications can only be rejected "
            "or marked withdrawn.",
        )
    # From an active stage, any other stage is allowed.
    return MoveCheck(True)
