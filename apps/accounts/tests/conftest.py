"""Fixtures for the auth flows.

``force_login`` is deliberately not used here. It leaves no allauth authentication records in
the session, so every reauthentication and MFA check treats the session as one that never
authenticated, and the pages under test behave nothing like they do for a real customer.

allauth's rate limits count in the cache, which is per process in the test settings, so the
cache is cleared between tests: without that, a test that deliberately trips ``login_failed``
would lock out whichever test ran next.
"""

from __future__ import annotations

import pytest
from allauth.account.models import EmailAddress
from django.core.cache import cache
from django.test import Client

from apps.common.factories import StaffUserFactory, UserFactory

PASSWORD = "correct-horse-9812"


@pytest.fixture(autouse=True)
def _clear_rate_limits():
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def browser():
    return Client()


def verified(user):
    """Give a user the verified primary address allauth's mandatory verification demands."""
    EmailAddress.objects.update_or_create(
        user=user, email=user.email, defaults={"verified": True, "primary": True}
    )
    return user


@pytest.fixture
def customer(db):
    return verified(UserFactory(email="buyer@example.com", password=PASSWORD))


@pytest.fixture
def staff(db):
    return verified(StaffUserFactory(email="ops@example.com", password=PASSWORD))


def sign_in(browser, user, password=PASSWORD, **extra):
    """Sign in the way a customer does, through the form, so the session carries allauth's
    authentication records. Returns the response, which is a redirect on success and the
    re-rendered form on failure."""
    return browser.post("/accounts/login/", {"login": user.email, "password": password, **extra})


@pytest.fixture
def signed_in(browser, customer):
    response = sign_in(browser, customer)
    assert response.status_code == 302, "the fixture's own login must succeed"
    return browser
