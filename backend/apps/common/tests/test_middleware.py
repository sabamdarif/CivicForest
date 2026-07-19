"""RequestIDMiddleware + StaffAdminMiddleware (plan.md §11, §16)."""

from __future__ import annotations

import pytest
from allauth.mfa.models import Authenticator
from django.conf import settings
from django.test import Client

from apps.common.factories import StaffUserFactory, UserFactory

pytestmark = pytest.mark.django_db

ADMIN = "/" + settings.ADMIN_URL


# ─── Request-ID middleware ───────────────────────────────────────────────────
def test_request_id_generated_and_echoed():
    resp = Client().get("/healthz")
    assert resp.status_code == 200
    assert len(resp["X-Request-ID"]) == 32  # uuid4 hex


def test_inbound_request_id_is_reused():
    resp = Client().get("/healthz", headers={"X-Request-ID": "trace-me-123"})
    assert resp["X-Request-ID"] == "trace-me-123"


# ─── Staff admin gate ────────────────────────────────────────────────────────
def _totp(user):
    Authenticator.objects.create(user=user, type=Authenticator.Type.TOTP, data={})


def test_staff_without_mfa_gets_404():
    staff = StaffUserFactory()
    c = Client()
    c.force_login(staff)
    assert c.get(ADMIN).status_code == 404


def test_superuser_without_mfa_redirected_to_mfa_setup():
    root = StaffUserFactory(email="root@example.com", is_superuser=True)
    c = Client()
    c.force_login(root)
    resp = c.get(ADMIN)
    assert resp.status_code == 302
    assert resp["Location"] == f"{settings.FRONTEND_ORIGIN}/account/security"


def _plain_static(settings):
    # Whitenoise's manifest storage needs collectstatic; tests render the admin
    # without it.
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }


def test_staff_with_totp_reaches_admin(settings):
    _plain_static(settings)
    staff = StaffUserFactory()
    _totp(staff)
    c = Client()
    c.force_login(staff)
    assert c.get(ADMIN).status_code == 200


def test_staff_session_expiry_shortened(settings):
    _plain_static(settings)
    staff = StaffUserFactory()
    _totp(staff)
    c = Client()
    c.force_login(staff)
    c.get(ADMIN)
    assert c.session.get_expiry_age() <= settings.STAFF_SESSION_AGE


def test_non_staff_user_untouched_by_admin_gate():
    user = UserFactory()
    c = Client()
    c.force_login(user)
    # Not staff → middleware passes through; admin login page redirects.
    resp = c.get(ADMIN)
    assert resp.status_code == 302
    # And a customer path is unaffected entirely.
    assert c.get("/healthz").status_code == 200
