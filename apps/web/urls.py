"""URL routes of the web pages."""

from datetime import date

from django.urls import path, register_converter

from . import views


class IsoDateConverter:
    """A date in the URL, like 2026-10-07."""

    regex = r"\d{4}-\d{2}-\d{2}"

    def to_python(self, value: str) -> date:
        """Parse the URL text into a date."""
        return date.fromisoformat(value)  # A date like 2026-02-30 raises ValueError: a 404.

    def to_url(self, value: date | str) -> str:
        """Write a date as URL text."""
        return value.isoformat() if isinstance(value, date) else str(value)


register_converter(IsoDateConverter, "date")

app_name = "web"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("login/", views.Login.as_view(), name="login"),
    path("logout/", views.Logout.as_view(), name="logout"),
    path("reports/", views.report_list, name="reports"),
    path("reports/<date:day>/", views.report_detail, name="report"),
    path("news/", views.news_list, name="news"),
    path("ipos/", views.ipo_list, name="ipos"),
    path("ipos/<int:pk>/", views.ipo_detail, name="ipo"),
    path("markets/", views.markets, name="markets"),
    path("companies/", views.company_list, name="companies"),
    path("delivery/", views.delivery, name="delivery"),
    path("account/", views.account, name="account"),
]
