"""The back-office gate: `is_staff` plus a confirmed MFA step, or a 404.

A redirect would confirm the page exists to someone who may not see it, so every failure is a
404. `test_middleware.py` owns the admin-path variant; this owns `StaffRequiredMixin`.
"""

import pytest
from django.urls import reverse

from apps.common.factories import StaffUserFactory, UserFactory, login_staff_with_mfa

pytestmark = pytest.mark.django_db


@pytest.fixture
def url():
    return reverse("backoffice:dashboard")


def test_anonymous_is_told_nothing(client, url):
    assert client.get(url).status_code == 404


def test_signed_in_customer_is_told_nothing(client, url):
    client.force_login(UserFactory())

    assert client.get(url).status_code == 404


def test_staff_without_mfa_is_told_nothing(client, url):
    # is_staff alone is not enough: the session must have completed an MFA step.
    client.force_login(StaffUserFactory())

    assert client.get(url).status_code == 404


def test_staff_with_mfa_gets_in(client, url):
    login_staff_with_mfa(client)

    assert client.get(url).status_code == 200
