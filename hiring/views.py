from django.shortcuts import render

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


def skill_list(request):
    return _placeholder(request, "Skills", "skills")
