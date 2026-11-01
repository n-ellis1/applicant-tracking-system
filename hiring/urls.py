from django.urls import path

from . import views

app_name = "hiring"

urlpatterns = [
    path("", views.pipeline, name="pipeline"),
    path("candidates/", views.candidate_list, name="candidate_list"),
    path("jobs/", views.job_list, name="job_list"),
    path("jobs/new/", views.job_create, name="job_create"),
    path("jobs/<int:pk>/", views.job_detail, name="job_detail"),
    path("jobs/<int:pk>/edit/", views.job_edit, name="job_edit"),
    path("jobs/<int:pk>/delete/", views.job_delete, name="job_delete"),
    path("jobs/<int:pk>/close/", views.job_close, name="job_close"),
    path("jobs/<int:pk>/reopen/", views.job_reopen, name="job_reopen"),
    path("skills/", views.skill_list, name="skill_list"),
    path("skills/new/", views.skill_create, name="skill_create"),
    path("skills/<int:pk>/edit/", views.skill_edit, name="skill_edit"),
    path("skills/<int:pk>/delete/", views.skill_delete, name="skill_delete"),
]
