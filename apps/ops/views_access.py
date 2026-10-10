"""Ops pages for the feature permissions and the subscriptions of the users.

Staff users can look. Only a superuser can change something. Every change goes in the audit
trail and in the history of the subscription.
"""

from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ObjectDoesNotExist
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.access import features, service
from apps.access.models import Subscription
from apps.access.rules import Access
from apps.siteconfig import conf
from apps.web.datastar import read_filters

from . import audit
from .forms import SubscriptionGiveForm
from .permissions import staff_required, superuser_post_required

STATE_FILTERS = (
    ("", "All"),
    ("trial", "Trial"),
    ("active", "Active"),
    ("expired", "Ended"),
    ("none", "None"),
    ("staff", "Staff"),
)
STATE_NAMES = dict(STATE_FILTERS)


def _subscription_of(user) -> Subscription | None:
    """The subscription of a user, from the select_related cache if it is there."""
    try:
        return user.subscription
    except ObjectDoesNotExist:
        return None


def summary(user, now) -> dict:
    """The state of a user's subscription and the number of removed features, for a list."""
    access = Access(user, now, subscription=_subscription_of(user))  # No query for each row.
    blocked = {block.feature for block in user.feature_blocks.all()} & features.KEYS
    sub = access.subscription
    return {
        "state": access.state,
        "sub": sub,
        "days_left": sub.days_left(now) if sub else None,
        "removed": len(blocked),
    }


def panel(user, now=None) -> dict:
    """What the user page shows about access: the boxes, the subscription, and the history."""
    now = now or timezone.now()
    access = Access(user, now)
    return {
        "access": access,
        "sub": access.subscription,
        "days_left": access.subscription.days_left(now) if access.subscription else None,
        "feature_rows": [
            {"feature": feature, "allowed": feature.key not in access.blocked}
            for feature in features.FEATURES
        ],
        "sub_events": user.subscription_events.all()[:10],
        "require_subscription": conf.SUBSCRIPTIONS_REQUIRED,
        "give_form": SubscriptionGiveForm(),
    }


@staff_required
def subscription_list(request: HttpRequest) -> HttpResponse:
    """All users with the state of their subscription."""
    filters = read_filters(request, ("state",))
    chosen = filters["state"] if filters["state"] in STATE_NAMES else ""
    now = timezone.now()
    users = (
        get_user_model()
        .objects.select_related("subscription")
        .prefetch_related("feature_blocks")
        .order_by("username")
    )
    rows = [{"user": user, **summary(user, now)} for user in users]
    counts = {key: sum(1 for r in rows if r["state"] == key) for key, _label in STATE_FILTERS[1:]}
    if chosen:
        rows = [r for r in rows if r["state"] == chosen]
    context = {
        "rows": rows,
        "counts": [(key, label, counts[key]) for key, label in STATE_FILTERS[1:]],
        "chosen": chosen,
        "section": "subscriptions",
    }
    return render(request, "ops/subscriptions.html", context)


@superuser_post_required
def user_access_save(request: HttpRequest, pk: int) -> HttpResponse:
    """Save the feature boxes of a user. A box that is not ticked removes the feature."""
    user = get_object_or_404(get_user_model(), pk=pk)
    allowed = set(request.POST.getlist("allow"))
    blocked = features.KEYS - allowed
    try:
        added, removed = service.set_blocked(user, blocked, actor=request.user)
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("ops:user", pk=pk)
    parts = []
    if added:
        parts.append("removed: " + ", ".join(added))
    if removed:
        parts.append("given back: " + ", ".join(removed))
    if parts:
        audit.record(request.user, "change access", user.get_username(), "; ".join(parts), request)
        messages.success(request, f"Saved the features of {user.get_username()}.")
    else:
        messages.info(request, "No change.")
    return redirect("ops:user", pk=pk)


@superuser_post_required
def user_subscription_give(request: HttpRequest, pk: int) -> HttpResponse:
    """Give or change the subscription of a user."""
    user = get_object_or_404(get_user_model(), pk=pk)
    form = SubscriptionGiveForm(request.POST)
    if not form.is_valid():
        errors = "; ".join(str(e) for errs in form.errors.values() for e in errs)
        messages.error(request, f"Not saved: {errors}")
        return redirect("ops:user", pk=pk)
    data = form.cleaned_data
    try:
        sub = service.give(
            user,
            data["kind"],
            days=data["days"],
            ends_on=data["ends_on"],
            actor=request.user,
            note=data["note"],
        )
    except ValueError as exc:
        messages.error(request, f"Not saved: {exc}")
        return redirect("ops:user", pk=pk)
    end = sub.ends_at.strftime("%Y-%m-%d") if sub.ends_at else "no end"
    audit.record(
        request.user,
        "give subscription",
        user.get_username(),
        f"{sub.kind}, ends {end}" + (f" ({data['note']})" if data["note"] else ""),
        request,
    )
    messages.success(request, f"Saved the subscription of {user.get_username()}.")
    return redirect("ops:user", pk=pk)


@superuser_post_required
def user_subscription_end(request: HttpRequest, pk: int) -> HttpResponse:
    """End the subscription of a user now."""
    user = get_object_or_404(get_user_model(), pk=pk)
    try:
        service.end_now(user, actor=request.user, note=request.POST.get("note", "")[:200])
    except ValueError as exc:
        messages.error(request, str(exc))
        return redirect("ops:user", pk=pk)
    audit.record(request.user, "end subscription", user.get_username(), "", request)
    messages.success(request, f"The subscription of {user.get_username()} is ended.")
    return redirect("ops:user", pk=pk)
