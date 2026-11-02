import pytest

from hiring.stages import ACTIVE_STAGES, FINAL_STAGES, MoveCheck, Stage, check_move

# Pairs of (current, target), built per rule so every relevant pair is covered.
# R-2: skip forward to any later active stage or to Hired (one step included).
FORWARD = [
    (current, target)
    for index, current in enumerate(ACTIVE_STAGES)
    for target in (*ACTIVE_STAGES[index + 1 :], Stage.HIRED)
]
# R-3: back to any earlier active stage.
BACKWARD = [
    (current, target)
    for index, current in enumerate(ACTIVE_STAGES)
    for target in ACTIVE_STAGES[:index]
]
# R-4: Rejected or Withdrawn from any active stage.
TO_REJECTED_OR_WITHDRAWN = [
    (current, target)
    for current in ACTIVE_STAGES
    for target in (Stage.REJECTED, Stage.WITHDRAWN)
]
# R-5: no direct moves between final outcomes.
FINAL_TO_FINAL = [
    (current, target)
    for current in FINAL_STAGES
    for target in FINAL_STAGES
    if current != target
]


def _ids(pairs):
    return [f"{current.label} -> {target.label}" for current, target in pairs]


def test_rule_pairs_cover_the_expected_moves():
    # Guards the generated lists above against an off-by-one.
    assert (Stage.APPLIED, Stage.SCREENING) in FORWARD
    assert (Stage.APPLIED, Stage.INTERVIEW) in FORWARD
    assert (Stage.OFFER, Stage.HIRED) in FORWARD
    assert (Stage.OFFER, Stage.OFFER) not in FORWARD
    assert (Stage.OFFER, Stage.APPLIED) in BACKWARD
    assert (Stage.APPLIED, Stage.APPLIED) not in BACKWARD
    assert len(FORWARD) == 15
    assert len(BACKWARD) == 10
    assert len(TO_REJECTED_OR_WITHDRAWN) == 10
    assert len(FINAL_TO_FINAL) == 6


@pytest.mark.parametrize(
    ("current", "target"),
    FORWARD + BACKWARD + TO_REJECTED_OR_WITHDRAWN,
    ids=_ids(FORWARD + BACKWARD + TO_REJECTED_OR_WITHDRAWN),
)
def test_open_job_allows_moves_from_active_stages(current, target):
    assert check_move(current, target, job_open=True) == MoveCheck(True)


@pytest.mark.parametrize(
    ("current", "target"), FINAL_TO_FINAL, ids=_ids(FINAL_TO_FINAL)
)
def test_open_job_blocks_moves_between_final_outcomes(current, target):
    assert check_move(current, target, job_open=True) == MoveCheck(
        False,
        "A finished application can't move straight to another outcome. "
        "Reopen it first.",
    )


@pytest.mark.parametrize("stage", list(Stage), ids=[s.label for s in Stage])
def test_moving_to_the_current_stage_is_blocked(stage):
    assert check_move(stage, stage, job_open=True) == MoveCheck(
        False, f"The application is already at {stage.label}."
    )


# Reopening a finished application comes in Phase 9; until then it's blocked.
FINAL_TO_ACTIVE = [
    (current, target) for current in FINAL_STAGES for target in ACTIVE_STAGES
]


@pytest.mark.parametrize(
    ("current", "target"), FINAL_TO_ACTIVE, ids=_ids(FINAL_TO_ACTIVE)
)
def test_moves_from_final_to_active_stages_are_blocked(current, target):
    assert check_move(current, target, job_open=True) == MoveCheck(
        False, "This application is finished. Reopen it before moving it."
    )


@pytest.mark.parametrize(
    ("current", "target"),
    [("bogus", Stage.APPLIED), (Stage.APPLIED, "bogus"), (Stage.APPLIED, "")],
)
def test_unknown_stage_values_are_rejected(current, target):
    with pytest.raises(ValueError):
        check_move(current, target, job_open=True)


# R-11 and R-12: on a closed job, active applications can only be rejected or
# withdrawn. Every other move from an active stage is blocked, including Hired.
CLOSED_JOB_BLOCKED = FORWARD + BACKWARD


@pytest.mark.parametrize(
    ("current", "target"),
    TO_REJECTED_OR_WITHDRAWN,
    ids=_ids(TO_REJECTED_OR_WITHDRAWN),
)
def test_closed_job_allows_rejected_or_withdrawn_from_active_stages(current, target):
    assert check_move(current, target, job_open=False) == MoveCheck(True)


@pytest.mark.parametrize(
    ("current", "target"), CLOSED_JOB_BLOCKED, ids=_ids(CLOSED_JOB_BLOCKED)
)
def test_closed_job_blocks_every_other_move_from_active_stages(current, target):
    assert check_move(current, target, job_open=False) == MoveCheck(
        False,
        "This job is closed, so its applications can only be rejected "
        "or marked withdrawn.",
    )


def test_closed_job_blocks_moving_to_hired_from_offer():
    # R-12 spelled out: even the natural last step can't hire on a closed job.
    assert not check_move(Stage.OFFER, Stage.HIRED, job_open=False).allowed


@pytest.mark.parametrize(
    ("current", "target", "reason"),
    [
        (
            Stage.INTERVIEW,
            Stage.INTERVIEW,
            "The application is already at Interview.",
        ),
        (
            Stage.REJECTED,
            Stage.WITHDRAWN,
            "A finished application can't move straight to another outcome. "
            "Reopen it first.",
        ),
    ],
    ids=["same stage", "final to final"],
)
def test_closed_job_keeps_the_more_specific_reason(current, target, reason):
    assert check_move(current, target, job_open=False) == MoveCheck(False, reason)
