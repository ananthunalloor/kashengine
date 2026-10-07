"""The web pages. They only show data. They do not change it (except login and logout)."""

from datetime import date

from django.conf import settings
from django.contrib.auth.views import LoginView, LogoutView
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.delivery.models import DeliveryLog
from apps.delivery.service import configured_chat_ids
from apps.ipos.models import Ipo
from apps.markets.evaluation import accuracy_stats
from apps.markets.trading import today_ist
from apps.reports.models import Report

from . import queries
from .datastar import is_datastar, querystring, read_filters, read_page, signals_json

NEWS_FILTERS = ("q", "sentiment", "source", "page")
IPO_FILTERS = ("q", "status", "verdict", "category", "page")
COMPANY_FILTERS = ("q", "page")


class Login(LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True


class Logout(LogoutView):
    """Logout needs a POST request."""


def _page(request, items, filters):
    return Paginator(items, settings.WEB_PAGE_SIZE).get_page(read_page(filters))


def _filter_view(request, template, partial, names, build_queryset, extra=None):
    """A list page with filters. A Datastar request gets only the list. Others get the page."""
    filters = read_filters(request, names)
    page = _page(request, build_queryset(filters), filters)
    context = {
        "filters": filters,
        "page": page,
        "qs": querystring(filters),
        "signals": signals_json(filters),
        **(extra() if extra else {}),
    }
    return render(request, partial if is_datastar(request) else template, context)


# --- Pages ---------------------------------------------------------------------------------


def dashboard(request):
    return render(request, "web/dashboard.html", queries.dashboard_data())


def report_list(request):
    filters = read_filters(request, ("page",))
    page = _page(request, Report.objects.all(), filters)
    return render(request, "web/report_list.html", {"page": page})


def report_detail(request, day: date):
    report = get_object_or_404(Report, date=day)
    context = {
        "report": report,
        "older": Report.objects.filter(date__lt=day).order_by("-date").first(),
        "newer": Report.objects.filter(date__gt=day).order_by("date").first(),
        "deliveries": DeliveryLog.objects.filter(report=report),
        "data": report.data or {},
    }
    return render(request, "web/report_detail.html", context)


def news_list(request):
    return _filter_view(
        request,
        "web/news.html",
        "web/_news_results.html",
        NEWS_FILTERS,
        queries.news_queryset,
        extra=lambda: {
            "sources": queries.news_sources(),
            "sentiments": queries.SENTIMENT_FILTERS,
        },
    )


def ipo_list(request):
    return _filter_view(
        request,
        "web/ipos.html",
        "web/_ipo_results.html",
        IPO_FILTERS,
        queries.ipo_queryset,
        extra=lambda: {
            "tabs": queries.IPO_TABS,
            "verdicts": queries.VERDICT_FILTERS,
            "categories": queries.CATEGORY_FILTERS,
        },
    )


def ipo_detail(request, pk: int):
    ipo = get_object_or_404(Ipo, pk=pk)
    inputs = ipo.score_inputs or {}
    context = {
        "ipo": ipo,
        "facts": queries.ipo_facts(ipo, timezone.now()),
        "signals": inputs.get("signals", []),
        "notes": inputs.get("notes", []),
    }
    return render(request, "web/ipo_detail.html", context)


def markets(request):
    context = {
        "stats": accuracy_stats(),
        "history": queries.prediction_history(),
        "quotes": queries.latest_quotes(),
    }
    return render(request, "web/markets.html", context)


def company_list(request):
    return _filter_view(
        request,
        "web/companies.html",
        "web/_company_results.html",
        COMPANY_FILTERS,
        queries.company_queryset,
    )


def delivery(request):
    context = {
        "logs": DeliveryLog.objects.select_related("report")[:50],
        "chat_count": len(configured_chat_ids()),
        "today": today_ist(),
    }
    return render(request, "web/delivery.html", context)
