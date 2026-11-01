from django.contrib import admin

from .forms import JobOpeningForm, SkillForm
from .models import JobOpening, Skill


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
