from urllib.parse import urlencode

from django.core.paginator import Paginator
from django.db.models import ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import services
from .forms import CandidateForm, JobOpeningForm, SkillForm
from .models import Candidate, JobOpening, Skill

# Placeholder pages for the top navigation. Later phases replace each one.


def _placeholder(request, title, active_nav):
    return render(
        request,
        "hiring/placeholder.html",
        {"title": title, "active_nav": active_nav},
    )


def pipeline(request):
    return _placeholder(request, "Pipeline", "pipeline")


# Candidates


def candidate_list(request):
    q = request.GET.get("q", "").strip()
    candidates = Candidate.objects.all()
    if q:
        candidates = candidates.filter(
            Q(first_name__icontains=q)
            | Q(last_name__icontains=q)
            | Q(email__icontains=q)
        )

    page_obj = Paginator(candidates, 25).get_page(request.GET.get("page"))
    # Page links carry the search so paging keeps the same view.
    return render(
        request,
        "hiring/candidate_list.html",
        {
            "candidates": page_obj.object_list,
            "page_obj": page_obj,
            "page_query": urlencode({"q": q}) if q else "",
            "q": q,
            "active_nav": "candidates",
        },
    )


def candidate_create(request):
    form = CandidateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        candidate = form.save()
        return redirect("hiring:candidate_detail", pk=candidate.pk)
    return render(
        request,
        "hiring/candidate_form.html",
        {"form": form, "title": "New candidate", "active_nav": "candidates"},
    )


def candidate_detail(request, pk):
    candidate = get_object_or_404(Candidate, pk=pk)
    return render(
        request,
        "hiring/candidate_detail.html",
        {"candidate": candidate, "active_nav": "candidates"},
    )


def candidate_edit(request, pk):
    candidate = get_object_or_404(Candidate, pk=pk)
    form = CandidateForm(request.POST or None, instance=candidate)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect("hiring:candidate_detail", pk=candidate.pk)
    return render(
        request,
        "hiring/candidate_form.html",
        {
            "form": form,
            "candidate": candidate,
            "title": "Edit candidate",
            "active_nav": "candidates",
        },
    )


def candidate_delete(request, pk):
    candidate = get_object_or_404(Candidate, pk=pk)
    if request.method == "POST":
        candidate.delete()
        return redirect("hiring:candidate_list")
    return render(
        request,
        "hiring/candidate_confirm_delete.html",
        {"candidate": candidate, "active_nav": "candidates"},
    )


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


def _next_or(request, default):
    # Only follow a return address on this site, never an external one.
    next_url = request.POST.get("next") or request.GET.get("next", "")
    if url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return default


def job_close(request, pk):
    job = get_object_or_404(JobOpening, pk=pk)
    job_detail = reverse("hiring:job_detail", args=[pk])
    if request.method == "POST":
        services.close_job(job)
        return redirect(_next_or(request, job_detail))
    next_url = _next_or(request, "")
    return render(
        request,
        "hiring/job_confirm_close.html",
        {
            "job": job,
            # Applications arrive in a later phase.
            "active_count": 0,
            "next": next_url,
            "cancel_url": next_url or job_detail,
            "active_nav": "jobs",
        },
    )


@require_POST
def job_reopen(request, pk):
    job = get_object_or_404(JobOpening, pk=pk)
    services.reopen_job(job)
    return redirect(_next_or(request, reverse("hiring:job_detail", args=[pk])))


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
