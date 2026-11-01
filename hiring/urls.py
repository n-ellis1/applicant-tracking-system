from django.urls import path

from . import views

app_name = "hiring"

urlpatterns = [
    path("", views.pipeline, name="pipeline"),
    path("candidates/", views.candidate_list, name="candidate_list"),
    path("jobs/", views.job_list, name="job_list"),
    path("skills/", views.skill_list, name="skill_list"),
]
