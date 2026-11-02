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


# R-6 and R-10: Hired and Rejected reopen only to the stage before that outcome,
# and only on an open job. Missing or invalid history blocks the reopen.
REOPEN_CLOSED_JOB_REASON = (
    "This job is closed. Reopen the job before reopening this application."
)


def _reopen_cases():
    cases = []
    for current in (Stage.HIRED, Stage.REJECTED):
        for before in ACTIVE_STAGES:
            wrong_target = MoveCheck(
                False,
                f"A {current.label} application reopens only to {before.label}, "
                "the stage it was in before that outcome.",
            )
            for target in ACTIVE_STAGES:
                for job_open in (True, False):
                    if target != before:
                        expected = wrong_target
                    elif job_open:
                        expected = MoveCheck(True)
                    else:
                        expected = MoveCheck(False, REOPEN_CLOSED_JOB_REASON)
                    cases.append(
                        pytest.param(
                            current,
                            before,
                            target,
                            job_open,
                            expected,
                            id=f"{current.label} (from {before.label}) -> "
                            f"{target.label}, job {'open' if job_open else 'closed'}",
                        )
                    )
        for before in (None, "", "bogus", Stage.WITHDRAWN, Stage.HIRED, Stage.REJECTED):
            cases.append(
                pytest.param(
                    current,
                    before,
                    Stage.APPLIED,
                    True,
                    MoveCheck(
                        False,
                        "The stage history doesn't show which stage came before "
                        f"{current.label}, so this application can't be reopened.",
                    ),
                    id=f"{current.label} (from {before!r}) -> Applied, missing history",
                )
            )
    return cases


@pytest.mark.parametrize(
    ("current", "before", "target", "job_open", "expected"), _reopen_cases()
)
def test_hired_and_rejected_reopen_only_to_the_previous_stage_on_an_open_job(
    current, before, target, job_open, expected
):
    assert (
        check_move(current, target, job_open=job_open, stage_before_outcome=before)
        == expected
    )


# R-7, R-8 and R-9: Withdrawn reopens to Applied, and from then on the
# application can never skip forward. Single steps (including Offer -> Hired),
# backward moves and ending the application stay allowed.
WITHDRAWN_REOPEN_REASON = (
    "A Withdrawn application reopens only to Applied, so it repeats every stage."
)
FORWARD_PATH = (*ACTIVE_STAGES, Stage.HIRED)


def _no_skip_reason(step):
    return (
        "This application was reopened after being withdrawn, so it can't skip "
        f"stages. It can only move forward to {step.label}."
    )


def _withdrawn_cases():
    cases = []
    # Reopening Withdrawn, whether or not it was reopened from Withdrawn before.
    for restricted in (False, True):
        for target in ACTIVE_STAGES:
            for job_open in (True, False):
                if target != Stage.APPLIED:
                    expected = MoveCheck(False, WITHDRAWN_REOPEN_REASON)
                elif job_open:
                    expected = MoveCheck(True)
                else:
                    expected = MoveCheck(False, REOPEN_CLOSED_JOB_REASON)
                cases.append(
                    pytest.param(
                        Stage.WITHDRAWN,
                        target,
                        job_open,
                        restricted,
                        None,
                        expected,
                        id=f"Withdrawn -> {target.label}, "
                        f"job {'open' if job_open else 'closed'}, "
                        f"{'restricted' if restricted else 'unrestricted'}",
                    )
                )
    # A restricted application's moves from every active stage on an open job.
    for current in ACTIVE_STAGES:
        for target in Stage:
            if target == current:
                continue
            step = FORWARD_PATH[FORWARD_PATH.index(current) + 1]
            is_skip = target in FORWARD_PATH and FORWARD_PATH.index(
                target
            ) > FORWARD_PATH.index(step)
            expected = (
                MoveCheck(False, _no_skip_reason(step)) if is_skip else MoveCheck(True)
            )
            cases.append(
                pytest.param(
                    current,
                    target,
                    True,
                    True,
                    None,
                    expected,
                    id=f"restricted {current.label} -> {target.label}",
                )
            )
    # The restriction doesn't change where Hired and Rejected reopen to.
    for current in (Stage.HIRED, Stage.REJECTED):
        cases.append(
            pytest.param(
                current,
                Stage.INTERVIEW,
                True,
                True,
                Stage.INTERVIEW,
                MoveCheck(True),
                id=f"restricted {current.label} (from Interview) -> Interview",
            )
        )
    return cases


@pytest.mark.parametrize(
    ("current", "target", "job_open", "restricted", "before", "expected"),
    _withdrawn_cases(),
)
def test_withdrawn_reopens_to_applied_and_never_skips_forward_again(
    current, target, job_open, restricted, before, expected
):
    assert (
        check_move(
            current,
            target,
            job_open=job_open,
            stage_before_outcome=before,
            reopened_from_withdrawn=restricted,
        )
        == expected
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
