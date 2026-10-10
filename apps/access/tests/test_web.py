"""The web pages follow the feature and subscription rules."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.access import service
from apps.access.models import FeatureBlock, Subscription
from apps.siteconfig import service as site_service

pytestmark = pytest.mark.django_db

DS = {"Datastar-Request": "true"}
FEATURE_PAGES = {
    "reports": reverse("web:reports"),
    "news": reverse("web:news"),
    "ipos": reverse("web:ipos"),
    "markets": reverse("web:markets"),
    "companies": reverse("web:companies"),
    "delivery": reverse("web:delivery"),
}


def _require():
    site_service.save({"SUBSCRIPTIONS_REQUIRED": True})


def _page(client, url, **kwargs) -> str:
    return client.get(url, **kwargs).content.decode()


# Defaults


def test_a_new_user_can_open_every_page(member_client):
    for url in [*FEATURE_PAGES.values(), reverse("web:dashboard"), reverse("web:account")]:
        assert member_client.get(url).status_code == 200


def test_the_menu_has_every_feature_by_default(member_client):
    page = _page(member_client, reverse("web:dashboard"))

    for url in FEATURE_PAGES.values():
        assert f'href="{url}"' in page
    assert f'href="{reverse("web:account")}"' in page


# One removed feature


@pytest.mark.parametrize("feature", sorted(FEATURE_PAGES))
def test_a_removed_feature_gives_a_403_page_and_the_others_work(member, member_client, feature):
    FeatureBlock.objects.create(user=member, feature=feature)

    response = member_client.get(FEATURE_PAGES[feature])

    assert response.status_code == 403
    assert "Not on your account" in response.content.decode()
    for other, url in FEATURE_PAGES.items():
        if other != feature:
            assert member_client.get(url).status_code == 200


def test_the_detail_pages_follow_their_feature(member, member_client):
    FeatureBlock.objects.create(user=member, feature="ipos")
    FeatureBlock.objects.create(user=member, feature="reports")

    assert member_client.get(reverse("web:ipo", args=[1])).status_code == 403
    assert member_client.get(reverse("web:report", args=["2026-01-05"])).status_code == 403


def test_a_datastar_request_for_a_removed_feature_gets_plain_text(member, member_client):
    FeatureBlock.objects.create(user=member, feature="news")

    response = member_client.get(reverse("web:news"), headers=DS)

    assert response.status_code == 403
    assert response["Content-Type"].startswith("text/plain")
    assert "<html" not in response.content.decode()


def test_the_menu_hides_a_removed_feature(member, member_client):
    FeatureBlock.objects.create(user=member, feature="ipos")

    page = _page(member_client, reverse("web:dashboard"))

    assert f'href="{FEATURE_PAGES["ipos"]}"' not in page
    assert f'href="{FEATURE_PAGES["news"]}"' in page


def test_the_removal_works_at_once(member, member_client):
    assert member_client.get(FEATURE_PAGES["news"]).status_code == 200

    service.set_blocked(member, {"news"})

    assert member_client.get(FEATURE_PAGES["news"]).status_code == 403

    service.set_blocked(member, set())

    assert member_client.get(FEATURE_PAGES["news"]).status_code == 200


def test_the_dashboard_hides_the_parts_of_removed_features(member, member_client):
    url = reverse("web:dashboard")
    full = _page(member_client, url)
    assert 'id="news-title"' in full
    assert 'id="ipo-title"' in full
    assert "Outlook" in full or "No outlook yet" in full

    service.set_blocked(member, {"news"})
    assert 'id="news-title"' not in _page(member_client, url)
    assert 'id="ipo-title"' in _page(member_client, url)

    service.set_blocked(member, {"ipos"})
    assert 'id="ipo-title"' not in _page(member_client, url)

    service.set_blocked(member, {"markets"})
    page = _page(member_client, url)
    assert "No outlook yet" not in page
    assert "Last close" not in page


def test_a_user_without_any_feature_sees_a_welcome_page(member, member_client):
    service.set_blocked(member, {"reports", "news", "ipos", "markets", "companies", "delivery"})

    response = member_client.get(reverse("web:dashboard"))

    assert response.status_code == 200
    assert "No feature is on for your account" in response.content.decode()


def test_staff_ignore_blocks(staff, staff_client):
    FeatureBlock.objects.create(user=staff, feature="news")

    assert staff_client.get(FEATURE_PAGES["news"]).status_code == 200


# The subscription rule


def test_an_ended_trial_does_not_matter_while_the_rule_is_off(member_client, member, expire):
    expire(member)

    assert member_client.get(FEATURE_PAGES["news"]).status_code == 200


def test_a_locked_user_is_sent_to_the_account_page(member_client, member, expire):
    _require()
    expire(member)

    for url in [reverse("web:dashboard"), *FEATURE_PAGES.values()]:
        response = member_client.get(url)
        assert response.status_code == 302
        assert response.url == reverse("web:account")


def test_the_locked_user_can_read_the_account_page_and_log_out(member_client, member, expire):
    _require()
    expire(member)

    account = member_client.get(reverse("web:account"))
    page = account.content.decode()
    assert account.status_code == 200
    assert "Ended" in page
    assert "Ask the admin to turn on your subscription." in page
    assert "Locked until you subscribe" in page
    assert f'href="{FEATURE_PAGES["news"]}"' not in page  # The menu has no feature links.

    assert member_client.post(reverse("web:logout")).status_code == 302
    assert member_client.get(reverse("web:dashboard")).status_code == 302  # Logged out now.


def test_a_locked_datastar_request_gets_a_403(member_client, member, expire):
    _require()
    expire(member)

    assert member_client.get(FEATURE_PAGES["news"], headers=DS).status_code == 403


def test_a_user_can_log_in_when_locked(client, member, expire):
    _require()
    expire(member)

    response = client.post(
        reverse("web:login"), {"username": "member", "password": "pw-access-test-1"}
    )

    assert response.status_code == 302  # The login works. The next page shows the account.


def test_a_subscription_given_by_an_admin_opens_the_pages_again(member_client, member, expire):
    _require()
    expire(member)
    assert member_client.get(FEATURE_PAGES["news"]).status_code == 302

    service.give(member, "paid", days=30)

    assert member_client.get(FEATURE_PAGES["news"]).status_code == 200


def test_ending_the_subscription_locks_the_user(member_client, member):
    _require()
    assert member_client.get(FEATURE_PAGES["news"]).status_code == 200

    service.end_now(member)

    assert member_client.get(FEATURE_PAGES["news"]).status_code == 302


def test_staff_are_never_locked(staff_client, staff, expire):
    _require()
    expire(staff)

    assert staff_client.get(FEATURE_PAGES["news"]).status_code == 200
    assert staff_client.get(reverse("ops:overview")).status_code == 200


def test_the_rule_works_for_a_user_without_a_subscription_row(member_client, member):
    Subscription.objects.filter(user=member).delete()
    _require()

    assert member_client.get(FEATURE_PAGES["news"]).status_code == 302
    assert member_client.get(reverse("web:account")).status_code == 200


# The notice and the account page


def test_the_notice_shows_in_every_page_near_the_end(member_client, member):
    _require()
    service.give(member, "trial", days=1)  # About 8 days: no notice yet.
    assert "ends" not in _page(member_client, reverse("web:account")).split("<main")[0]

    member.subscription.ends_at = timezone.now() + timedelta(days=1, hours=2)
    member.subscription.save()

    page = _page(member_client, FEATURE_PAGES["news"])

    assert "Your trial ends in 2 days." in page


def test_no_notice_while_the_rule_is_off(member_client, member):

    member.subscription.ends_at = timezone.now() + timedelta(hours=2)
    member.subscription.save()

    assert "Your trial ends" not in _page(member_client, FEATURE_PAGES["news"])


def test_the_account_page_shows_the_trial_and_the_features(member, member_client):
    service.set_blocked(member, {"ipos"})

    page = _page(member_client, reverse("web:account"))

    assert "Trial" in page
    assert "7 days left" in page
    assert "A subscription is not required now." in page
    assert page.count("Included") == 5
    assert "Not on your account" in page


def test_the_account_page_shows_the_price_from_the_settings(member_client):
    site_service.save(
        {
            "SUBSCRIPTION_PRICE": 199,
            "SUBSCRIPTION_CURRENCY": "INR",
            "SUBSCRIPTION_PERIOD_DAYS": 30,
            "SUBSCRIPTION_CONTACT_TEXT": "Pay by UPI to the admin.",
        }
    )

    page = _page(member_client, reverse("web:account"))

    assert "199 INR" in page
    assert "30 days" in page
    assert "Pay by UPI to the admin." in page


def test_the_account_page_for_staff(staff_client):
    page = _page(staff_client, reverse("web:account"))

    assert "staff account" in page
    assert "Included" in page


def test_the_account_page_for_a_paid_user(member_client, member):
    service.give(member, "paid", days=30)

    page = _page(member_client, reverse("web:account"))

    assert "Active" in page
    assert "Paid" not in page.split("Subscription")[0]


def test_other_places_are_not_affected(client, member_client, member, expire):
    _require()
    expire(member)

    assert client.get(reverse("health")).status_code == 200
    assert member_client.get(reverse("ops:overview")).status_code == 403  # Staff only, as before.
