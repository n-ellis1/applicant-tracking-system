"""Data-changing hiring operations, shared by app views and admin."""

from django.utils import timezone

from .models import JobOpening


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
