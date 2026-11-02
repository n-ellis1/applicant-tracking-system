from urllib.parse import urlencode

from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Count, Max, ProtectedError, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_GET, require_POST

from . import services
from .forms import (
    CandidateApplicationForm,
    CandidateForm,
    JobApplicationForm,
    JobOpeningForm,
    MoveForm,
    SkillForm,
)
from .models import Application, Candidate, JobOpening, Skill
from .stages import ACTIVE_STAGES, FINAL_STAGES, Stage, check_move, next_stage

# Pipeline workspace


def _progress_steps(application, history):
    """Steps for the stage progress indicator, in pipeline order."""
    stage = application.stage
    if stage in FINAL_STAGES:
        # Mark the active stages reached before the outcome.
        before = history[-1].old_stage if history else ""
        reached = ACTIVE_STAGES.index(before) if before in ACTIVE_STAGES else -1
        tone = "success" if stage == Stage.HIRED else "error"
        last = {"label": Stage(stage).label, "tone": tone, "current": True}
    else:
        reached = ACTIVE_STAGES.index(stage)
        last = {"label": Stage.HIRED.label, "tone": "", "current": False}
    steps = [
        {
            "label": active.label,
            "tone": "primary" if index <= reached else "",
            "current": active == stage,
        }
        for index, active in enumerate(ACTIVE_STAGES)
    ]
    return [*steps, last]


def _stage_actions(application, facts):
    """The panel's moves, sorted by the stage rules into actions and reasons."""
    job_open = application.job.status == JobOpening.Status.OPEN
    step = next_stage(application.stage)
    actions = {
        "advance": None,
        "reopen": None,
        "end_moves": [],
        "other_moves": [],
        "blocked_moves": [],
    }
    for target in Stage:
        if target == application.stage:
            continue
        check = check_move(
            application.stage, target, job_open=job_open, **facts._asdict()
        )
        if not check.allowed:
            actions["blocked_moves"].append({"stage": target, "reason": check.reason})
        elif target in services.REASON_STAGES:
            # Only the inline confirmation boxes reach Rejected and Withdrawn.
            actions["end_moves"].append(target)
        elif target == step:
            actions["advance"] = target
        elif application.stage in FINAL_STAGES:
            # The rules allow a finished application exactly one reopen target.
            actions["reopen"] = target
        else:
            actions["other_moves"].append(target)
    return actions


APPLICATION_TABS = [("active", "Active"), ("finished", "Finished"), ("all", "All")]


def _workspace(request, job, selected=None, move_form=None):
    # job is None only on the landing page when no job is open.
    # The sidebar filter defaults to the job's status so its link is visible;
    # the landing page defaults to Open.
    jobs_filter = request.GET.get("jobs")
    if jobs_filter not in dict(JOB_STATUS_FILTERS):
        jobs_filter = job.status if job is not None else JobOpening.Status.OPEN
    tab = request.GET.get("tab")
    if tab not in dict(APPLICATION_TABS):
        tab = "active"
    q = request.GET.get("q", "").strip()
    # Filter links keep whatever is displayed, so switching never selects a
    # different job: on the landing page they target the landing job's URL.
    if selected is not None:
        filter_base = reverse("hiring:application_detail", args=[selected.pk])
    elif job is not None:
        filter_base = reverse("hiring:pipeline_job", args=[job.pk])
    else:
        filter_base = reverse("hiring:pipeline")
    jobs = JobOpening.objects.with_in_progress_count()
    # Links that keep the displayed view keep the tab and search too.
    list_query = urlencode(_list_query(jobs_filter, tab, q))
    context = {
        "job": job,
        "jobs_filter": jobs_filter,
        "filter_links": [
            (value, label, f"{filter_base}?{urlencode(_list_query(value, tab, q))}")
            for value, label in JOB_STATUS_FILTERS
        ],
        "show_all_url": f"{filter_base}?{urlencode(_list_query('all', tab, q))}",
        "list_query": list_query,
        "filter_base": filter_base,
        "open_jobs": [
            j
            for j in jobs
            if j.status == JobOpening.Status.OPEN and jobs_filter != "closed"
        ],
        "closed_jobs": [
            j
            for j in jobs
            if j.status == JobOpening.Status.CLOSED and jobs_filter != "open"
        ],
        "any_closed_jobs": any(j.status == JobOpening.Status.CLOSED for j in jobs),
        # The filter never changes the displayed job, but it can hide its link.
        "job_hidden": job is not None and jobs_filter not in ("all", job.status),
        "selected": selected,
        # Close and reopen return here: the displayed job or application with
        # the current sidebar filter, tab and search. Never the move URL a
        # failed move renders.
        "return_url": f"{filter_base}?{list_query}",
        "active_nav": "pipeline",
    }
    if job is not None:
        # Most recent stage change first, from history; the newest
        # application breaks a tie.
        applications = (
            job.applications.select_related("candidate")
            .annotate(last_stage_change=Max("history__changed_at"))
            .order_by("-last_stage_change", "-pk")
        )
        if q:
            applications = applications.filter(
                Q(candidate__first_name__icontains=q)
                | Q(candidate__last_name__icontains=q)
                | Q(candidate__email__icontains=q)
            )
        applications = list(applications)
        # Tab counts reflect the job and search, before the tab is applied.
        by_tab = {
            "active": [a for a in applications if a.stage in ACTIVE_STAGES],
            "finished": [a for a in applications if a.stage in FINAL_STAGES],
            "all": applications,
        }
        context["tab"] = tab
        context["q"] = q
        context["tabs"] = [
            {
                "value": value,
                "label": label,
                "count": len(by_tab[value]),
                "url": f"{filter_base}?{urlencode(_list_query(jobs_filter, value, q))}",
            }
            for value, label in APPLICATION_TABS
        ]
        # Tells an empty tab or search apart from a job with no applications.
        context["job_has_applications"] = job.applications.exists()
        # One group per stage that has applications, in pipeline order.
        context["groups"] = [
            {"stage": stage, "applications": members}
            for stage in Stage
            if (members := [a for a in by_tab[tab] if a.stage == stage])
        ]
    if selected is not None:
        history = list(selected.history.select_related("changed_by"))
        context["history"] = history
        context["progress"] = _progress_steps(selected, history)
        facts = services.stage_facts(selected.stage, history)
        context["facts"] = facts
        context["actions"] = _stage_actions(selected, facts)
        if move_form is not None:
            context["move_errors"] = [
                message
                for messages in move_form.errors.values()
                for message in messages
            ]
    return render(request, "hiring/pipeline.html", context)


def _list_query(jobs_filter, tab, q):
    # Always carries the sidebar filter. The Active tab and an empty search
    # are the defaults, so they're left out.
    query = {"jobs": jobs_filter}
    if tab != "active":
        query["tab"] = tab
    if q:
        query["q"] = q
    return query


def pipeline(request):
    # Land on the first open job by title.
    job = JobOpening.objects.filter(status=JobOpening.Status.OPEN).first()
    return _workspace(request, job)


def pipeline_job(request, job_pk):
    return _workspace(request, get_object_or_404(JobOpening, pk=job_pk))


def job_application_create(request, job_pk):
    job = get_object_or_404(JobOpening, pk=job_pk)
    form = JobApplicationForm(request.POST or None, job=job)
    if request.method == "POST" and form.is_valid():
        try:
            application = services.create_application(
                candidate=form.cleaned_data["candidate"],
                job=job,
                applied_on=form.cleaned_data["applied_on"],
                changed_by=request.user,
            )
        except ValidationError as error:
            # A duplicate is about the chosen candidate; a closed job isn't.
            form.add_error("candidate" if error.code == "duplicate" else None, error)
        else:
            return redirect("hiring:application_detail", pk=application.pk)
    workspace_url = reverse("hiring:pipeline_job", args=[job.pk])
    return render(
        request,
        "hiring/application_form.html",
        {
            "form": form,
            "picker": form["candidate"],
            "empty_message": "Every candidate has already applied to this job.",
            "unavailable": (
                services.CLOSED_JOB if job.status == JobOpening.Status.CLOSED else ""
            ),
            "cancel_url": workspace_url,
            "title": f"New application for {job}",
            "active_nav": "pipeline",
        },
    )


# Candidates


def candidate_list(request):
    q = request.GET.get("q", "").strip()
    # Django drops Meta.ordering from GROUP BY queries, so order explicitly.
    candidates = Candidate.objects.annotate(
        application_count=Count("applications")
    ).order_by(*Candidate._meta.ordering)
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
        {
            "candidate": candidate,
            "applications": candidate.applications.select_related("job").order_by(
                "-created_at", "-pk"
            ),
            "active_nav": "candidates",
        },
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


def candidate_application_create(request, pk):
    candidate = get_object_or_404(Candidate, pk=pk)
    form = CandidateApplicationForm(request.POST or None, candidate=candidate)
    if request.method == "POST" and form.is_valid():
        try:
            application = services.create_application(
                candidate=candidate,
                job=form.cleaned_data["job"],
                applied_on=form.cleaned_data["applied_on"],
                changed_by=request.user,
            )
        except ValidationError as error:
            form.add_error("job", error)
        else:
            return redirect("hiring:application_detail", pk=application.pk)
    return render(
        request,
        "hiring/application_form.html",
        {
            "form": form,
            "picker": form["job"],
            "empty_message": "There are no open jobs this candidate hasn't applied to.",
            "cancel_url": reverse("hiring:candidate_detail", args=[candidate.pk]),
            "title": f"New application for {candidate}",
            "active_nav": "candidates",
        },
    )


def candidate_delete(request, pk):
    candidate = get_object_or_404(Candidate, pk=pk)
    if request.method == "POST":
        try:
            candidate.delete()
        except ProtectedError:
            pass  # The page below explains which applications block it.
        else:
            return redirect("hiring:candidate_list")
    return render(
        request,
        "hiring/candidate_confirm_delete.html",
        {
            "candidate": candidate,
            "applications": candidate.applications.select_related("job"),
            "active_nav": "candidates",
        },
    )


# Applications


@require_GET
def application_detail(request, pk):
    # The workspace with the application's job open and the application
    # selected. Candidate and job are shown but never editable.
    application = get_object_or_404(
        Application.objects.select_related("candidate", "job"), pk=pk
    )
    return _workspace(request, application.job, application)


@require_POST
def application_move(request, pk):
    application = get_object_or_404(
        Application.objects.select_related("candidate", "job"), pk=pk
    )
    form = MoveForm(request.POST)
    if form.is_valid():
        try:
            services.move_application(
                application,
                form.cleaned_data["stage"],
                changed_by=request.user,
                reason=form.cleaned_data["reason"],
            )
        except ValidationError as error:
            form.add_error(None, error)
        else:
            # Back to the same workspace URL, keeping a valid sidebar filter,
            # tab and search.
            url = reverse("hiring:application_detail", args=[pk])
            query = {}
            jobs_filter = request.GET.get("jobs")
            if jobs_filter in dict(JOB_STATUS_FILTERS):
                query["jobs"] = jobs_filter
            tab = request.GET.get("tab")
            if tab in dict(APPLICATION_TABS) and tab != "active":
                query["tab"] = tab
            if q := request.GET.get("q", "").strip():
                query["q"] = q
            if query:
                url += "?" + urlencode(query)
            return redirect(url)
    # The move changed nothing; show why, with actions for the current stage.
    return _workspace(request, application.job, application, move_form=form)


# Jobs


JOB_STATUS_FILTERS = [("open", "Open"), ("closed", "Closed"), ("all", "All")]


def job_list(request):
    q = request.GET.get("q", "").strip()
    status = request.GET.get("status")
    if status not in dict(JOB_STATUS_FILTERS):
        status = "open"

    jobs = JobOpening.objects.with_in_progress_count()
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
        try:
            job.delete()
        except ProtectedError:
            pass  # The page below explains which applications block it.
        else:
            return redirect("hiring:job_list")
    return render(
        request,
        "hiring/job_confirm_delete.html",
        {
            "job": job,
            "applications": job.applications.select_related("candidate"),
            "active_nav": "jobs",
        },
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
    job = get_object_or_404(JobOpening.objects.with_in_progress_count(), pk=pk)
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
            "active_count": job.in_progress_count,
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
