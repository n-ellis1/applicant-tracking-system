from django.contrib import admin

from .forms import SkillForm
from .models import Skill


class SkillAdminForm(SkillForm):
    """The app's trimming and duplicate check, with admin's own widgets."""

    class Meta(SkillForm.Meta):
        widgets = {}


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    form = SkillAdminForm
    search_fields = ["name"]
