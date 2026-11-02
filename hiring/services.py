"""Data-changing hiring operations, shared by app views and admin."""

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Application, JobOpening, StageHistoryEntry
from .stages import Stage, check_move

DUPLICATE_APPLICATION = "This candidate has already applied to this job."
CLOSED_JOB = "This job is closed and can't accept new applications."
REASON_NOT_ALLOWED = "A reason can only be given when rejecting or withdrawing."

# Only moves that end an application can carry a reason.
REASON_STAGES = (Stage.REJECTED, Stage.WITHDRAWN)


def _has_applied(candidate, job):
    # Any existing application counts, whatever its stage.
    return Application.objects.filter(candidate=candidate, job=job).exists()


def create_application(*, candidate, job, applied_on, changed_by):
    """Record an application at Applied with its initial history entry.

    Raises ValidationError if the application isn't allowed.
    """
    # Read the status from the database: the caller's job may be stale.
    status = JobOpening.objects.values_list("status", flat=True).get(pk=job.pk)
    if status == JobOpening.Status.CLOSED:
        raise ValidationError(CLOSED_JOB, code="closed_job")
    if _has_applied(candidate, job):
        raise ValidationError(DUPLICATE_APPLICATION, code="duplicate")
    try:
        with transaction.atomic():
            application = Application.objects.create(
                candidate=candidate,
                job=job,
                applied_on=applied_on,
                stage=Stage.APPLIED,
            )
            StageHistoryEntry.objects.create(
                application=application,
                new_stage=Stage.APPLIED,
                changed_by=changed_by,
            )
    except IntegrityError:
        # A concurrent submission can pass the check above and hit the unique
        # constraint. Only that is a duplicate; any other failure propagates.
        if _has_applied(candidate, job):
            raise ValidationError(DUPLICATE_APPLICATION, code="duplicate") from None
        raise
    return application


def move_application(application, target, *, changed_by, reason=""):
    """Move an application to target and record the move in its history.

    Raises ValidationError if the move isn't allowed.
    """
    if reason and target not in REASON_STAGES:
        raise ValidationError(REASON_NOT_ALLOWED, code="reason_not_allowed")
    with transaction.atomic():
        # Check against the database: the caller's page may be stale.
        current = Application.objects.select_related("job").get(pk=application.pk)
        check = check_move(
            current.stage,
            target,
            job_open=current.job.status == JobOpening.Status.OPEN,
        )
        if not check.allowed:
            raise ValidationError(check.reason, code="blocked_move")
        old_stage = current.stage
        current.stage = target
        current.save(update_fields=["stage", "updated_at"])
        StageHistoryEntry.objects.create(
            application=current,
            old_stage=old_stage,
            new_stage=target,
            changed_by=changed_by,
            reason=reason,
        )
    application.stage = current.stage
    return current


def close_job(job):
    # Closing again (a stale page or double submit) keeps the original date.
    if job.status == JobOpening.Status.CLOSED:
        return
    job.status = JobOpening.Status.CLOSED
    job.closed_at = timezone.now()
    job.save(update_fields=["status", "closed_at", "updated_at"])


def reopen_job(job):
    # Reopening an open job (a stale page or double submit) changes nothing.
    if job.status == JobOpening.Status.OPEN:
        return
    job.status = JobOpening.Status.OPEN
    job.closed_at = None
    job.save(update_fields=["status", "closed_at", "updated_at"])
