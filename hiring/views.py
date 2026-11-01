from django.shortcuts import get_object_or_404, redirect, render

from .forms import SkillForm
from .models import Skill

# Placeholder pages for the top navigation. Later phases replace each one.


def _placeholder(request, title, active_nav):
    return render(
        request,
        "hiring/placeholder.html",
        {"title": title, "active_nav": active_nav},
    )


def pipeline(request):
    return _placeholder(request, "Pipeline", "pipeline")


def candidate_list(request):
    return _placeholder(request, "Candidates", "candidates")


def job_list(request):
    return _placeholder(request, "Jobs", "jobs")


# Skills


def skill_list(request):
    return render(
        request,
        "hiring/skill_list.html",
        {"skills": Skill.objects.all(), "active_nav": "skills"},
    )


def skill_create(request):
    form = SkillForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("hiring:skill_list")
    return render(
        request,
        "hiring/skill_form.html",
        {"form": form, "title": "New skill", "active_nav": "skills"},
    )


def skill_edit(request, pk):
    skill = get_object_or_404(Skill, pk=pk)
    form = SkillForm(request.POST or None, instance=skill)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("hiring:skill_list")
    return render(
        request,
        "hiring/skill_form.html",
        {"form": form, "title": "Rename skill", "active_nav": "skills"},
    )


def skill_delete(request, pk):
    skill = get_object_or_404(Skill, pk=pk)
    if request.method == "POST":
        skill.delete()
        return redirect("hiring:skill_list")
    return render(
        request,
        "hiring/skill_confirm_delete.html",
        {"skill": skill, "active_nav": "skills"},
    )
