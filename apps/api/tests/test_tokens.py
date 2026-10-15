from datetime import timedelta

import pytest
from django.utils import timezone

from apps.api import tokens
from apps.api.models import ApiToken
from apps.siteconfig import conf

pytestmark = pytest.mark.django_db


def test_issue_returns_the_secret_once_and_stores_only_a_hash(member):
    row, raw = tokens.issue(member, "Excel")
    assert raw.startswith(f"ke_{row.prefix}_")
    assert len(raw) == 3 + 8 + 1 + 48
    assert raw not in {row.token_hash, row.prefix, row.name}
    assert row.token_hash == tokens.digest(raw)
    assert raw.split("_")[2] not in str(row.__dict__)


def test_a_new_token_expires_after_the_setting(member, settings):
    row, _raw = tokens.issue(member, "a")
    settings.API_TOKEN_EXPIRY_DAYS = 90
    assert row.expires_at is not None
    assert timedelta(days=89) < row.expires_at - timezone.now() <= timedelta(days=90)


def test_expiry_zero_means_no_end(member, settings):
    settings.API_TOKEN_EXPIRY_DAYS = 0

    conf.invalidate()
    row, _raw = tokens.issue(member, "a")
    assert row.expires_at is None


def test_the_empty_name_is_refused(member):
    with pytest.raises(ValueError, match="name"):
        tokens.issue(member, "   ")


def test_the_limit_of_active_tokens(member, settings):
    settings.API_TOKEN_MAX_PER_USER = 2

    conf.invalidate()
    tokens.issue(member, "a")
    row, _ = tokens.issue(member, "b")
    with pytest.raises(tokens.TokenLimitError):
        tokens.issue(member, "c")
    tokens.revoke(row)
    tokens.issue(member, "c")


def test_authenticate_accepts_a_good_token(member):
    row, raw = tokens.issue(member, "a")
    assert tokens.authenticate(raw).pk == row.pk


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "garbage",
        "ke_zzzzzzzz_" + "0" * 48,
        "ke_" + "0" * 8 + "_" + "0" * 48,
        "xx_" + "0" * 8 + "_" + "0" * 48,
    ],
)
def test_authenticate_refuses_bad_text(raw):
    with pytest.raises(tokens.TokenError) as info:
        tokens.authenticate(raw)
    assert info.value.code == "invalid_token"


def test_authenticate_refuses_a_wrong_secret_with_a_right_prefix(member):
    row, _raw = tokens.issue(member, "a")
    wrong = f"ke_{row.prefix}_" + "0" * 48
    with pytest.raises(tokens.TokenError) as info:
        tokens.authenticate(wrong)
    assert info.value.code == "invalid_token"


def test_authenticate_gives_the_same_message_for_every_invalid_case(member):
    row, _raw = tokens.issue(member, "a")
    messages = set()
    for text in ("nope", f"ke_{row.prefix}_" + "1" * 48, "ke_" + "2" * 8 + "_" + "3" * 48):
        with pytest.raises(tokens.TokenError) as info:
            tokens.authenticate(text)
        messages.add(info.value.message)
    assert len(messages) == 1


def test_an_expired_token_has_its_own_code(member):
    row, raw = tokens.issue(member, "a")
    ApiToken.objects.filter(pk=row.pk).update(expires_at=timezone.now() - timedelta(seconds=1))
    with pytest.raises(tokens.TokenError) as info:
        tokens.authenticate(raw)
    assert info.value.code == "token_expired"


def test_a_revoked_token_is_invalid(member):
    row, raw = tokens.issue(member, "a")
    assert tokens.revoke(row) is True
    assert tokens.revoke(row) is False
    with pytest.raises(tokens.TokenError) as info:
        tokens.authenticate(raw)
    assert info.value.code == "invalid_token"


def test_an_inactive_user_loses_the_token(member):
    _row, raw = tokens.issue(member, "a")
    member.is_active = False
    member.save()
    with pytest.raises(tokens.TokenError):
        tokens.authenticate(raw)


def test_a_password_change_ends_all_tokens(member):
    _row, raw = tokens.issue(member, "a")
    member.set_password("another-password-9")
    member.save()
    with pytest.raises(tokens.TokenError) as info:
        tokens.authenticate(raw)
    assert info.value.code == "invalid_token"


def test_revoke_all(member, staff):
    tokens.issue(member, "a")
    tokens.issue(member, "b")
    _row, other = tokens.issue(staff, "c")
    assert tokens.revoke_all(member) == 2
    assert tokens.active_tokens(member) == []
    assert tokens.authenticate(other)


def test_touch_writes_at_most_once_a_minute(member):
    row, _raw = tokens.issue(member, "a")
    now = timezone.now()
    tokens.touch(row, now)
    first = ApiToken.objects.get(pk=row.pk).last_used_at
    tokens.touch(row, now + timedelta(seconds=30))
    assert ApiToken.objects.get(pk=row.pk).last_used_at == first
    tokens.touch(row, now + timedelta(seconds=61))
    assert ApiToken.objects.get(pk=row.pk).last_used_at > first


def test_the_database_has_no_plain_secret(member):
    _row, raw = tokens.issue(member, "a")
    secret = raw.rsplit("_", 1)[1]
    for value in ApiToken.objects.values_list("token_hash", "prefix", "name"):
        assert all(secret not in str(part) for part in value)
