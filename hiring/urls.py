from django.urls import path

from . import views

app_name = "hiring"

urlpatterns = [
    path("", views.pipeline, name="pipeline"),
    path("candidates/", views.candidate_list, name="candidate_list"),
    path("jobs/", views.job_list, name="job_list"),
    path("skills/", views.skill_list, name="skill_list"),
    path("skills/new/", views.skill_create, name="skill_create"),
    path("skills/<int:pk>/edit/", views.skill_edit, name="skill_edit"),
    path("skills/<int:pk>/delete/", views.skill_delete, name="skill_delete"),
]
