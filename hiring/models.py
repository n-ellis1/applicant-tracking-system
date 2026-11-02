from django.db import models
from django.db.models import ProtectedError
from django.db.models.functions import Lower


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
