"""URL routes of the Ops pages."""

from django.urls import path

from . import views

app_name = "ops"

urlpatterns = [
    path("", views.overview, name="overview"),
    path("jobs/", views.job_list, name="jobs"),
    path("jobs/<slug:key>/run/", views.job_run, name="job_run"),
    path("runs/", views.run_list, name="runs"),
    path("runs/<int:pk>/", views.run_detail, name="run"),
    path("logs/", views.log_view, name="logs"),
    path("metrics/", views.metric_view, name="metrics"),
    path("users/", views.user_list, name="users"),
    path("users/<int:pk>/", views.user_detail, name="user"),
    path("users/<int:pk>/sessions/end/", views.user_end_sessions, name="user_end_sessions"),
    path("users/<int:pk>/active/", views.user_set_active, name="user_set_active"),
    path("logins/", views.login_list, name="logins"),
    path("audit/", views.audit_list, name="audit"),
    path("config/", views.config_view, name="config"),
]
