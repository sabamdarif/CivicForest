"""MFA guarantees: a TOTP code cannot be replayed, and a recovery code is spent once.

Driven through the real forms, never force_login, because these guarantees rest on allauth's
authentication records and its used-code ledger, and force_login writes neither. The ledger lives
in the cache, cleared between tests by the autouse fixture in conftest, so a code marked used in
one test cannot poison the next.
"""

from __future__ import annotations

import time

import pytest
from allauth.mfa import app_settings
from allauth.mfa.models import Authenticator
from allauth.mfa.totp.internal.auth import format_hotp_value, hotp_value

from apps.common.factories import StaffUserFactory

from .conftest import PASSWORD, verified

pytestmark = pytest.mark.django_db

LOGIN = "/accounts/login/"
LOGOUT = "/accounts/logout/"
AUTHENTICATE = "/accounts/2fa/authenticate/"
ACTIVATE = "/accounts/2fa/totp/activate/"
TRUST = "/accounts/2fa/trust/"
ACCOUNT = "/account/"


def _totp_code(secret: str) -> str:
    """A currently-valid 6-digit code for `secret`, through allauth's own HOTP helpers.

    Pinned to allauth's internals on purpose; revisit on an allauth upgrade if the module moves.
    """
    counter = int(time.time()) // app_settings.TOTP_PERIOD
    return format_hotp_value(hotp_value(secret, counter))


def _enrol_totp(browser) -> str:
    """Walk the real activate page: GET seeds the secret in the session, POST confirms a code.
    Enrolling the first authenticator auto-generates the account's recovery codes."""
    browser.get(ACTIVATE)
    secret = browser.session["mfa.totp.secret"]
    browser.post(ACTIVATE, {"code": _totp_code(secret)})
    return secret


def _authenticate(browser, user, code):
    """Sign in through the real form, then answer the MFA prompt with `code`. The trust prompt is
    declined (no ``action=trust``) so no trust cookie is set and the next login needs MFA again."""
    browser.post(LOGIN, {"login": user.email, "password": PASSWORD})
    response = browser.post(AUTHENTICATE, {"code": code})
    browser.post(TRUST, {})
    return response


@pytest.fixture
def totp_user(db):
    """A verified user signed in with a confirmed TOTP authenticator, then signed out."""
    from django.test import Client

    user = verified(StaffUserFactory(email="mfa@example.com", password=PASSWORD))
    browser = Client()
    browser.post(LOGIN, {"login": user.email, "password": PASSWORD})
    secret = _enrol_totp(browser)
    browser.post(LOGOUT)
    return user, secret


def test_a_totp_code_cannot_be_replayed(totp_user):
    from django.test import Client

    user, secret = totp_user
    code = _totp_code(secret)
    browser = Client()

    assert _authenticate(browser, user, code).status_code == 302
    browser.post(LOGOUT)

    # The same code, still within its period, is refused: the ledger marked it used at first use.
    replay = _authenticate(browser, user, code)

    assert replay.status_code == 200
    assert browser.get(ACCOUNT).status_code == 302, "the replayed code must not sign anyone in"


def test_a_recovery_code_is_single_use(totp_user):
    from django.test import Client

    user, _ = totp_user
    codes = (
        Authenticator.objects.get(user=user, type=Authenticator.Type.RECOVERY_CODES)
        .wrap()
        .get_unused_codes()
    )
    browser = Client()

    assert _authenticate(browser, user, codes[0]).status_code == 302
    browser.post(LOGOUT)

    reuse = _authenticate(browser, user, codes[0])
    assert reuse.status_code == 200
    assert browser.get(ACCOUNT).status_code == 302, "a spent recovery code must not sign anyone in"
    browser.post(LOGOUT)

    # A different, unspent code still works, so only the used one was consumed.
    assert _authenticate(browser, user, codes[1]).status_code == 302
