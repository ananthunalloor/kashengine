"""The public introduction stays separate from the protected application."""

import pytest
from django.urls import reverse

from apps.siteconfig import service as site_service

pytestmark = pytest.mark.django_db


def test_landing_is_public_and_explains_the_capabilities(client):
    response = client.get("/")

    assert response.status_code == 200
    assert response.resolver_match.url_name == "landing"
    assert "web/landing.html" in [template.name for template in response.templates]
    assert response.text.count('<article class="capability-card">') == 6
    assert response.text.count("<details>") == 6
    for name in ("news", "markets", "ipos", "companies", "reports", "delivery"):
        assert f'href="{reverse(f"web:{name}")}"' in response.text
    for anchor in ("capabilities", "how-it-works", "principles"):
        assert f'id="{anchor}"' in response.text
    assert "Illustrative preview" in response.text
    assert "Not financial advice." in response.text
    assert f'href="{reverse("web:login")}"' in response.text
    assert f'href="{reverse("docs")}"' in response.text


def test_dashboard_still_requires_login(client):
    assert reverse("web:dashboard") == "/dashboard/"
    response = client.get(reverse("web:dashboard"))

    assert response.status_code == 302
    assert response["Location"] == f"{reverse('web:login')}?next=/dashboard/"


def test_login_brand_links_back_to_the_landing_page(client):
    response = client.get(reverse("web:login"))

    assert f'href="{reverse("web:landing")}"' in response.text


def test_landing_links_authenticated_users_to_the_dashboard(client, django_user_model):
    user = django_user_model.objects.create_user(username="landing-user")
    client.force_login(user)

    response = client.get(reverse("web:landing"))

    assert response.status_code == 200
    assert "Open dashboard" in response.text
    assert f'href="{reverse("web:dashboard")}"' in response.text


def test_landing_remains_open_when_a_subscription_expires(client, django_user_model, expire):
    site_service.save({"SUBSCRIPTIONS_REQUIRED": True})
    user = django_user_model.objects.create_user(username="expired-landing-user")
    expire(user)
    client.force_login(user)

    assert client.get(reverse("web:landing")).status_code == 200
    assert client.get(reverse("web:dashboard")).status_code == 302
