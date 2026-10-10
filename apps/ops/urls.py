"""URL routes of the Ops pages."""

from django.urls import path

from . import views, views_access, views_settings

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
    path("users/<int:pk>/access/", views_access.user_access_save, name="user_access"),
    path(
        "users/<int:pk>/subscription/give/",
        views_access.user_subscription_give,
        name="user_subscription_give",
    ),
    path(
        "users/<int:pk>/subscription/end/",
        views_access.user_subscription_end,
        name="user_subscription_end",
    ),
    path("subscriptions/", views_access.subscription_list, name="subscriptions"),
    path("logins/", views.login_list, name="logins"),
    path("logins/unlock/", views.lockout_unlock, name="lockout_unlock"),
    path("audit/", views.audit_list, name="audit"),
    path("config/", views.config_view, name="config"),
    path("settings/", views_settings.settings_index, name="settings"),
    path("settings/<slug:group>/", views_settings.settings_group, name="settings_group"),
    path("schedule/", views_settings.schedule_list, name="schedule"),
    path("schedule/add/", views_settings.schedule_add, name="schedule_add"),
    path("schedule/reset/", views_settings.schedule_reset, name="schedule_reset"),
    path("schedule/<int:pk>/", views_settings.schedule_edit, name="schedule_edit"),
    path("schedule/<int:pk>/toggle/", views_settings.schedule_toggle, name="schedule_toggle"),
    path("schedule/<int:pk>/delete/", views_settings.schedule_delete, name="schedule_delete"),
    path("feeds/", views_settings.feed_list, name="feeds"),
    path("feeds/<int:pk>/toggle/", views_settings.feed_toggle, name="feed_toggle"),
    path("feeds/<int:pk>/delete/", views_settings.feed_delete, name="feed_delete"),
    path("instruments/", views_settings.instrument_list, name="instruments"),
    path("instruments/<int:pk>/", views_settings.instrument_save, name="instrument_save"),
    path(
        "instruments/<int:pk>/delete/", views_settings.instrument_delete, name="instrument_delete"
    ),
]
