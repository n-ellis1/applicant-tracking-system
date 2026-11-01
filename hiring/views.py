from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.db.models import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render

from .forms import JobOpeningForm, SkillForm
from .models import JobOpening, Skill

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


# Jobs


JOB_STATUS_FILTERS = [("open", "Open"), ("closed", "Closed"), ("all", "All")]


def job_list(request):
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status")
    if status not in dict(JOB_STATUS_FILTERS):
        status = "open"

    jobs = JobOpening.objects.all()
    if status != "all":
        jobs = jobs.filter(status=status)
    if q:
        jobs = jobs.filter(title__icontains=q)

    page_obj = Paginator(jobs, 25).get_page(request.GET.get("page"))
    # Page links carry the search and filter so paging keeps the same view.
    kept = {"q": q, "status": status} if q else {"status": status}
    return render(
        request,
        "hiring/job_list.html",
        {
            "jobs": page_obj.object_list,
            "page_obj": page_obj,
            "page_query": urlencode(kept),
            "q": q,
            "status": status,
            "status_filters": JOB_STATUS_FILTERS,
            "active_nav": "jobs",
        },
    )


def job_create(request):
    form = JobOpeningForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        job = form.save()
        return redirect("hiring:job_detail", pk=job.pk)
    return render(
        request,
        "hiring/job_form.html",
        {"form": form, "title": "New job", "active_nav": "jobs"},
    )


def job_detail(request, pk):
    job = get_object_or_404(JobOpening, pk=pk)
    return render(
        request,
        "hiring/job_detail.html",
        {"job": job, "skills": job.skills.all(), "active_nav": "jobs"},
    )


def job_edit(request, pk):
    job = get_object_or_404(JobOpening, pk=pk)
    form = JobOpeningForm(request.POST or None, instance=job)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("hiring:job_detail", pk=job.pk)
    return render(
        request,
        "hiring/job_form.html",
        {"form": form, "job": job, "title": "Edit job", "active_nav": "jobs"},
    )


def job_delete(request, pk):
    job = get_object_or_404(JobOpening, pk=pk)
    if request.method == "POST":
        job.delete()
        return redirect("hiring:job_list")
    return render(
        request,
        "hiring/job_confirm_delete.html",
        {"job": job, "active_nav": "jobs"},
    )


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
        try:
            skill.delete()
        except ProtectedError:
            pass  # The page below explains which jobs use it.
        else:
            return redirect("hiring:skill_list")
    return render(
        request,
        "hiring/skill_confirm_delete.html",
        {"skill": skill, "used_by": skill.jobs.all(), "active_nav": "skills"},
    )
