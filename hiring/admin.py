from django.contrib import admin
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.html import format_html, format_html_join
from django.utils.text import capfirst

from .forms import ApplicationDetailsForm, CandidateForm, JobOpeningForm, SkillForm
from .models import Application, Candidate, JobOpening, Skill, StageHistoryEntry


class SkillAdminForm(SkillForm):
    """The app's trimming and duplicate check, with admin's own widgets."""

    class Meta(SkillForm.Meta):
        widgets = {}


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    form = SkillAdminForm
    search_fields = ["name"]

    def get_deleted_objects(self, objs, request):
        # List the jobs using these skills as protected, so admin's single and
        # bulk delete pages refuse with its "cannot delete" message.
        deleted, model_count, perms_needed, protected = super().get_deleted_objects(
            objs, request
        )
        jobs = JobOpening.objects.filter(skills__in=objs).distinct()
        protected = [*protected, *(f"Job opening: {job}" for job in jobs)]
        return deleted, model_count, perms_needed, protected


class JobOpeningAdminForm(JobOpeningForm):
    """The app's job fields and validation, with admin's own widgets."""

    class Meta(JobOpeningForm.Meta):
        widgets = {}


@admin.register(JobOpening)
class JobOpeningAdmin(admin.ModelAdmin):
    form = JobOpeningAdminForm
    list_display = ["title", "department", "employment_type", "status", "closed_at"]
    list_filter = ["status", "employment_type"]
    search_fields = ["title"]
    filter_horizontal = ["skills"]
    # Status and closed date change only by closing and reopening the job.
    readonly_fields = ["status", "closed_at", "created_at", "updated_at"]


class CandidateAdminForm(CandidateForm):
    """The app's email normalization and duplicate check, with admin's widgets."""

    class Meta(CandidateForm.Meta):
        widgets = {}


@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    form = CandidateAdminForm
    list_display = ["last_name", "first_name", "email", "source"]
    list_filter = ["source"]
    search_fields = ["first_name", "last_name", "email"]
    readonly_fields = ["created_at", "updated_at"]


class ApplicationAdminForm(ApplicationDetailsForm):
    """The app's editable fields and validation, with admin's own widgets."""

    class Meta(ApplicationDetailsForm.Meta):
        widgets = {}


@admin.register(Application)
class ApplicationAdmin(admin.ModelAdmin):
    form = ApplicationAdminForm
    list_display = ["candidate", "job", "stage", "applied_on"]
    list_filter = ["stage"]
    search_fields = [
        "candidate__first_name",
        "candidate__last_name",
        "candidate__email",
        "job__title",
    ]
    fields = [
        "candidate",
        "job",
        "stage",
        "applied_on",
        "notes",
        "stage_history",
        "created_at",
        "updated_at",
    ]
    # Candidate and job are fixed, and only the services change the stage.
    readonly_fields = [
        "candidate",
        "job",
        "stage",
        "stage_history",
        "created_at",
        "updated_at",
    ]

    def has_add_permission(self, request):
        # Applications are recorded through the app's service, which writes
        # the initial history entry.
        return False

    def save_model(self, request, obj, form, change):
        # Never write the stage: a move made since the page loaded stays.
        obj.save(update_fields=["applied_on", "notes", "updated_at"])

    @admin.display(description="Stage history")
    def stage_history(self, obj):
        rows = []
        for entry in obj.history.select_related("changed_by"):
            move = entry.get_new_stage_display()
            if entry.old_stage:
                move = f"{entry.get_old_stage_display()} → {move}"
            rows.append(
                (
                    date_format(
                        timezone.localtime(entry.changed_at), "DATETIME_FORMAT"
                    ),
                    move,
                    entry.changed_by.get_username(),
                    f" · Reason: {entry.reason}" if entry.reason else "",
                )
            )
        return format_html(
            "<ol>{}</ol>", format_html_join("", "<li>{} · {} · {}{}</li>", rows)
        )

    def get_deleted_objects(self, objs, request):
        # Admin's collector lists every history entry as protected. When none
        # of these applications ever moved, those are just their initial
        # entries, which the delete removes; anything else stays protected.
        deleted, model_count, perms_needed, protected = super().get_deleted_objects(
            objs, request
        )
        history = StageHistoryEntry._meta
        # Nobody has permission to delete history in admin; the never-moved
        # rule below decides instead, so a refusal lists the blocking entries.
        perms_needed.discard(history.verbose_name)
        pks = [obj.pk for obj in objs]
        if not Application.objects.filter(pk__in=pks).moved().exists():
            label = f"{capfirst(history.verbose_name)}:"
            protected = [p for p in protected if not p.startswith(label)]
            initial = StageHistoryEntry.objects.filter(application__in=pks)
            model_count[history.verbose_name_plural] = initial.count()
        return deleted, model_count, perms_needed, protected


@admin.register(StageHistoryEntry)
class StageHistoryEntryAdmin(admin.ModelAdmin):
    """View only: services create entries, and nothing edits or deletes them
    on their own."""

    list_display = ["application", "old_stage", "new_stage", "changed_at", "changed_by"]
    list_filter = ["new_stage"]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
