from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import ProtectedError
from django.db.models.functions import Lower
from django.utils import timezone

from .stages import Stage


def refuse_if_used(jobs):
    # The plain many-to-many link would otherwise drop a deleted skill from
    # its jobs silently. Any job counts, open or closed.
    if jobs.exists():
        raise ProtectedError(
            "Skills used by a job opening can't be deleted.", set(jobs)
        )


class SkillQuerySet(models.QuerySet):
    def delete(self):
        refuse_if_used(JobOpening.objects.filter(skills__in=self).distinct())
        return super().delete()


class Skill(models.Model):
    name = models.CharField(max_length=100)

    objects = SkillQuerySet.as_manager()

    class Meta:
        ordering = [Lower("name")]
        constraints = [
            models.UniqueConstraint(
                Lower("name"),
                name="unique_skill_name_ci",
                violation_error_message="A skill with this name already exists.",
            ),
        ]

    def __str__(self):
        return self.name

    def delete(self, *args, **kwargs):
        refuse_if_used(self.jobs.all())
        return super().delete(*args, **kwargs)


class JobOpening(models.Model):
    class EmploymentType(models.TextChoices):
        FULL_TIME = "full_time", "Full-time"
        PART_TIME = "part_time", "Part-time"
        CONTRACT = "contract", "Contract"
        INTERNSHIP = "internship", "Internship"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        CLOSED = "closed", "Closed"

    title = models.CharField(max_length=200)
    department = models.CharField(max_length=100)
    employment_type = models.CharField(max_length=20, choices=EmploymentType)
    description = models.TextField()
    location = models.CharField(max_length=200, blank=True)
    status = models.CharField(max_length=10, choices=Status, default=Status.OPEN)
    closed_at = models.DateTimeField(null=True, blank=True)
    skills = models.ManyToManyField(Skill, blank=True, related_name="jobs")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [Lower("title"), "pk"]

    def __str__(self):
        return self.title


class Candidate(models.Model):
    class Source(models.TextChoices):
        COMPANY_WEBSITE = "company_website", "Company Website"
        JOB_BOARD = "job_board", "Job Board"
        REFERRAL = "referral", "Referral"
        OTHER = "other", "Other"

    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField()
    phone = models.CharField(max_length=40, blank=True)
    location = models.CharField(max_length=200, blank=True)
    profile_url = models.URLField("profile URL", blank=True)
    notes = models.TextField(blank=True)
    # How the candidate first came to the company. Later applications never
    # change it.
    source = models.CharField(max_length=20, choices=Source)
    source_details = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = [Lower("last_name"), Lower("first_name"), "pk"]
        constraints = [
            models.UniqueConstraint(
                Lower("email"),
                name="unique_candidate_email_ci",
                violation_error_message="A candidate with this email already exists.",
            ),
        ]

    def __str__(self):
        return f"{self.first_name} {self.last_name}"


def validate_not_future(value):
    if value > timezone.localdate():
        raise ValidationError("The applied-on date can't be in the future.")


class Application(models.Model):
    # Candidate and job are fixed once created.
    candidate = models.ForeignKey(
        Candidate, on_delete=models.PROTECT, related_name="applications"
    )
    job = models.ForeignKey(
        JobOpening, on_delete=models.PROTECT, related_name="applications"
    )
    applied_on = models.DateField(
        default=timezone.localdate, validators=[validate_not_future]
    )
    notes = models.TextField(blank=True)
    # Only services.py writes the stage, together with its history entry.
    stage = models.CharField(max_length=20, choices=Stage)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["candidate", "job"],
                name="unique_application_candidate_job",
                violation_error_message=(
                    "This candidate has already applied to this job."
                ),
            ),
        ]

    def __str__(self):
        return f"{self.candidate} for {self.job}"


class StageHistoryEntry(models.Model):
    application = models.ForeignKey(
        Application, on_delete=models.PROTECT, related_name="history"
    )
    # Blank on the initial entry.
    old_stage = models.CharField(max_length=20, choices=Stage, blank=True)
    new_stage = models.CharField(max_length=20, choices=Stage)
    changed_at = models.DateTimeField(default=timezone.now)
    changed_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name="+")
    reason = models.TextField(blank=True)

    class Meta:
        ordering = ["changed_at", "pk"]
        verbose_name_plural = "stage history entries"

    def __str__(self):
        return f"{self.application}: {self.old_stage or '-'} -> {self.new_stage}"
