"""RequestIDMiddleware and StaffAdminMiddleware."""

from __future__ import annotations

import time

import pytest
from allauth.account.models import EmailAddress
from allauth.mfa.models import Authenticator
from allauth.mfa.totp.internal.auth import format_hotp_value, hotp_value
from django.conf import settings
from django.core.cache import cache
from django.test import Client

from apps.common.factories import StaffUserFactory, UserFactory

pytestmark = pytest.mark.django_db

ADMIN = "/" + settings.ADMIN_URL
PASSWORD = "correct-horse-9812"


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    # allauth's login rate limits and its used-code ledger both live in the cache, which is per
    # process in the test settings, so a code marked used in one test would poison the next.
    cache.clear()
    yield
    cache.clear()


def _totp_code(secret: str) -> str:
    """A currently-valid 6-digit code for `secret`, through allauth's own HOTP helpers.

    Pinned to allauth's internals on purpose: the test enrols and signs in the way a real staff
    member does. Revisit on an allauth upgrade if the auth module moves.
    """
    from allauth.mfa import app_settings

    counter = int(time.time()) // app_settings.TOTP_PERIOD
    return format_hotp_value(hotp_value(secret, counter))


def _verified_staff(**extra):
    staff = StaffUserFactory(password=PASSWORD, **extra)
    EmailAddress.objects.update_or_create(
        user=staff, email=staff.email, defaults={"verified": True, "primary": True}
    )
    return staff


def _sign_in(client, user, code=None):
    """Sign in through the real form so the session carries allauth's authentication records.

    When the user has TOTP, allauth redirects the credentials POST to the authenticate page; the
    second POST is the code, and only that makes the session MFA-authenticated.
    """
    client.post("/accounts/login/", {"login": user.email, "password": PASSWORD})
    if code is not None:
        client.post("/accounts/2fa/authenticate/", {"code": code})
        # MFA_TRUST_ENABLED puts a trust-this-browser prompt between the code and a finished
        # session; answering it is what completes the login.
        client.post("/accounts/2fa/trust/", {"action": "trust"})


def _enrol_totp(client) -> str:
    """Walk the real activate page: GET seeds the secret in the session, POST confirms a code."""
    client.get("/accounts/2fa/totp/activate/")
    secret = client.session["mfa.totp.secret"]
    client.post("/accounts/2fa/totp/activate/", {"code": _totp_code(secret)})
    return secret


# ─── Request-ID middleware ───────────────────────────────────────────────────
def test_request_id_generated_and_echoed():
    resp = Client().get("/healthz/")
    assert len(resp["X-Request-ID"]) == 32  # uuid4 hex


def test_inbound_request_id_is_reused():
    resp = Client().get("/healthz/", headers={"X-Request-ID": "trace-me-123"})
    assert resp["X-Request-ID"] == "trace-me-123"


@pytest.mark.parametrize("request_id", ["has spaces", "bad/value", "x" * 65, ""])
def test_invalid_inbound_request_id_is_replaced(request_id):
    resp = Client().get("/healthz/", headers={"X-Request-ID": request_id})

    assert len(resp["X-Request-ID"]) == 32
    assert resp["X-Request-ID"] != request_id


# ─── Staff admin gate ────────────────────────────────────────────────────────
# Driven through the real login form, never force_login: the gate reads allauth's authentication
# records, which force_login never writes, so it would treat every session as un-authenticated.
def test_staff_signed_in_without_mfa_gets_404():
    staff = _verified_staff()
    c = Client()
    _sign_in(c, staff)
    assert c.get(ADMIN).status_code == 404


def test_superuser_without_mfa_redirected_to_login():
    root = _verified_staff(email="root@example.com", is_superuser=True)
    c = Client()
    _sign_in(c, root)
    resp = c.get(ADMIN)
    assert resp.status_code == 302
    assert resp["Location"] == settings.LOGIN_URL


def test_staff_signed_in_with_a_totp_code_reaches_admin():
    from allauth.mfa.utils import decrypt

    staff = _verified_staff()
    c = Client()
    _sign_in(c, staff)
    secret = _enrol_totp(c)
    assert c.get(ADMIN).status_code == 404, "enrolment alone is not an MFA-authenticated session"

    # The secret leaves the session on activation, so read it back from the stored authenticator.
    stored = Authenticator.objects.get(user=staff, type=Authenticator.Type.TOTP)
    assert secret == decrypt(stored.data["secret"])

    c.post("/accounts/logout/")
    _sign_in(c, staff, code=_totp_code(secret))
    assert c.get(ADMIN).status_code == 200


def test_staff_session_expiry_shortened():
    staff = _verified_staff()
    c = Client()
    _sign_in(c, staff)
    c.get(ADMIN)
    assert c.session.get_expiry_age() <= settings.STAFF_SESSION_AGE


def test_non_staff_user_untouched_by_admin_gate():
    user = UserFactory(password=PASSWORD)
    EmailAddress.objects.update_or_create(
        user=user, email=user.email, defaults={"verified": True, "primary": True}
    )
    c = Client()
    _sign_in(c, user)
    # Not staff, so the middleware passes through; the admin login page redirects.
    resp = c.get(ADMIN)
    assert resp.status_code == 302
    # And a customer path is unaffected entirely.
    assert "X-Request-ID" in c.get("/healthz/")
