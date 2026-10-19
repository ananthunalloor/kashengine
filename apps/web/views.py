"""The web pages. They show data.

Three actions change data: login, logout, and the make and revoke of API tokens on the Account
page.
"""

from datetime import date
from typing import TYPE_CHECKING, cast

from django.contrib import messages
from django.contrib.auth.decorators import login_not_required
from django.contrib.auth.views import LoginView, LogoutView
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache

from apps.access import features
from apps.access.middleware import access_for
from apps.api import tokens
from apps.api.models import ApiToken
from apps.delivery.models import DeliveryLog
from apps.delivery.service import configured_chat_ids
from apps.ipos.models import Ipo
from apps.markets.evaluation import accuracy_stats
from apps.markets.trading import today_ist
from apps.ops import audit
from apps.ops.models import TaskRun
from apps.reports.builder import render_text
from apps.reports.models import Report
from apps.siteconfig import conf

from . import queries
from .datastar import is_datastar, querystring, read_filters, read_page, signals_json
from .decorators import post_only

if TYPE_CHECKING:
    from django.contrib.auth.base_user import AbstractBaseUser

NEWS_FILTERS = ("q", "sentiment", "source", "page")
IPO_FILTERS = ("q", "status", "verdict", "category", "page")
COMPANY_FILTERS = ("q", "page")


class Login(LoginView):
    """The login page."""

    template_name = "registration/login.html"
    redirect_authenticated_user = True


class Logout(LogoutView):
    """Logout needs a POST request."""


def _page(request, items, filters):
    return Paginator(items, conf.WEB_PAGE_SIZE).get_page(read_page(filters))


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


@login_not_required
def landing(request: HttpRequest) -> HttpResponse:
    """Introduce the app without exposing account or market data."""
    return render(request, "web/landing.html")


@never_cache
def react_app(request: HttpRequest) -> HttpResponse:
    """Serve the authenticated React application shell.

    Args:
        request: The incoming request.

    Returns:
        The rendered application shell.
    """
    return render(request, "web/spa.html")


def react_report(request: HttpRequest, day: date) -> HttpResponse:
    """Serve the Reports preview at a valid report URL without exposing its data.

    Args:
        request: The authenticated browser request.
        day: The report date parsed from the URL.

    Returns:
        The uncached application shell, or a 404 for an absent report.
    """
    get_object_or_404(Report.objects.only("id"), date=day)
    return react_app(request)


def dashboard(request):
    """The home page: today's outlook, news, IPOs, and quotes."""
    return render(request, "web/dashboard.html", queries.dashboard_data())


def react_ipo(request: HttpRequest, pk: int) -> HttpResponse:
    """Serve the IPO preview for an existing issue.

    Args:
        request: The authenticated browser request.
        pk: IPO primary key from the URL.

    Returns:
        The uncached application shell, or a 404 for a missing issue.
    """
    get_object_or_404(Ipo.objects.only("id"), pk=pk)
    return react_app(request)


def react_ops_run(request: HttpRequest, pk: int) -> HttpResponse:
    """Serve a run's preview shell; staff authentication is applied by the URL wrapper.

    Args:
        request: The staff browser request.
        pk: Run primary key from the URL.

    Returns:
        The uncached React shell without operational data, or a 404 for an absent run.
    """
    get_object_or_404(TaskRun.objects.only("id"), pk=pk)
    return react_app(request)


def report_list(request):
    """The list of daily reports."""
    filters = read_filters(request, ("page",))
    page = _page(request, Report.objects.all(), filters)
    return render(request, "web/report_list.html", {"page": page})


def report_detail(request, day: date):
    """One daily report, with its delivery log."""
    report = get_object_or_404(Report, date=day)
    context = {
        "report": report,
        "report_text": render_text(report.data) if report.data else report.text,
        "older": Report.objects.filter(date__lt=day).order_by("-date").first(),
        "newer": Report.objects.filter(date__gt=day).order_by("date").first(),
        "deliveries": DeliveryLog.objects.filter(report=report),
        "data": report.data or {},
    }
    return render(request, "web/report_detail.html", context)


def news_list(request):
    """The news list with filters."""
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
    """The IPO list with filters."""
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
    """One IPO with its facts and score signals."""
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
    """The markets page: prediction history, accuracy, and quotes."""
    context = {
        "stats": accuracy_stats(),
        "history": queries.prediction_history(),
        "quotes": queries.latest_quotes(),
    }
    return render(request, "web/markets.html", context)


def company_list(request):
    """The company list with a search filter."""
    return _filter_view(
        request,
        "web/companies.html",
        "web/_company_results.html",
        COMPANY_FILTERS,
        queries.company_queryset,
    )


def delivery(request):
    """The delivery page: the last send attempts."""
    context = {
        "logs": queries.latest_deliveries(),
        "chat_count": len(configured_chat_ids()),
        "today": today_ist(),
    }
    return render(request, "web/delivery.html", context)


def _account_context(request: HttpRequest, **extra) -> dict:
    """The context of the account page. `extra` adds keys, for example a new token."""
    access = access_for(request)
    sub = access.subscription
    rows = [
        {
            "feature": feature,
            "allowed": access.can(feature.key),
            "removed": feature.key in access.blocked,
        }
        for feature in features.FEATURES
    ]
    api_tokens = list(ApiToken.objects.filter(user=request.user)[: queries.ACCOUNT_TOKEN_ROWS])
    return {
        "access": access,
        "sub": sub,
        "days_left": sub.days_left(access.now) if sub else None,
        "rows": rows,
        "required": conf.SUBSCRIPTIONS_REQUIRED,
        "price": conf.SUBSCRIPTION_PRICE,
        "currency": conf.SUBSCRIPTION_CURRENCY,
        "period_days": conf.SUBSCRIPTION_PERIOD_DAYS,
        "contact": conf.SUBSCRIPTION_CONTACT_TEXT,
        "api_enabled": conf.API_ENABLED,
        "api_docs": conf.API_DOCS_ENABLED,
        "api_tokens": api_tokens,
        "active_tokens": sum(token.is_active(access.now) for token in api_tokens),
        "token_limit": conf.API_TOKEN_MAX_PER_USER,
        "token_days": conf.API_TOKEN_EXPIRY_DAYS,
        **extra,
    }


def account(request):
    """The account page: the subscription, the features, and the API tokens of the user.

    Every signed-in user can open it, also after the subscription has ended.
    """
    return render(request, "web/account.html", _account_context(request))


@post_only
def token_create(request: HttpRequest) -> HttpResponse:
    """Make an API token for the signed-in user and show it once.

    The answer is the account page itself (not a redirect), so the secret is never in a URL, a
    session or a log. The response is marked `no-store`.

    Args:
        request: A POST request with the field `name`.

    Returns:
        The account page. It shows the new token, or an error text.
    """
    user = cast("AbstractBaseUser", request.user)
    new_token = ""
    try:
        row, new_token = tokens.issue(user, request.POST.get("name", ""))
    except ValueError as exc:
        messages.error(request, str(exc))
    except tokens.TokenLimitError:
        messages.error(
            request,
            f"You have {conf.API_TOKEN_MAX_PER_USER} active tokens. "
            "Revoke one before you make a new one.",
        )
    else:
        audit.record(user, "api token create", user.get_username(), f"{row.display}", request)
    response = render(request, "web/account.html", _account_context(request, new_token=new_token))
    response["Cache-Control"] = "no-store"
    return response


@post_only
def token_revoke(request: HttpRequest, pk: int) -> HttpResponse:
    """Revoke one API token of the signed-in user.

    Args:
        request: A POST request.
        pk: The id of the token. A token of another user gives 404.

    Returns:
        A redirect to the account page.
    """
    token = get_object_or_404(ApiToken, pk=pk, user=request.user)
    if tokens.revoke(token):
        audit.record(
            request.user, "api token revoke", request.user.get_username(), token.display, request
        )
        messages.success(request, f"Token {token.display} is revoked.")
    return redirect("web:account")
