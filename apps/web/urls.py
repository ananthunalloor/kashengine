"""Canonical React product URLs; templates are isolated in the archive URLconf."""

from django.urls import path

from . import public_preview, signup, views
from .legacy_urls import IsoDateConverter  # noqa: F401  # Registers the shared date converter.

app_name = "web"

urlpatterns = [
    path("", public_preview.landing, name="landing"),
    path("login/", public_preview.PreviewLogin.as_view(), name="login"),
    path("signup/", signup.signup, name="signup"),
    path("legal/", signup.legal, name="legal"),
    path(
        "verify-email/<str:token>/",
        signup.verify_email,
        name="verify_email",
    ),
    path("logout/", views.Logout.as_view(), name="logout"),
    path("dashboard/", views.react_app, name="dashboard"),
    path("account/", views.react_app, name="account"),
    path("reports/", views.react_app, name="reports"),
    path("reports/<date:day>/", views.react_report, name="report"),
    path("news/", views.react_app, name="news"),
    path("ipos/", views.react_app, name="ipos"),
    path("ipos/<int:pk>/", views.react_ipo, name="ipo"),
    path("markets/", views.react_app, name="markets"),
    path("markets/live/", views.react_app, name="market_live"),
    path("companies/", views.react_app, name="companies"),
    path("companies/<int:pk>/", views.react_company, name="company"),
    path("delivery/", views.react_app, name="delivery"),
]
