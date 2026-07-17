"""Request/correlation-ID plumbing and staff admin hardening.

One request ID is generated (or taken from an inbound ``X-Request-ID``) per request,
stashed on a contextvar so log records and Celery tasks can pick it up, and echoed back
on the response — so a single failed checkout can be traced Caddy → Django → worker
(plan.md §16). ``StaffAdminMiddleware`` gates the admin path on confirmed TOTP MFA and
shortens staff sessions (plan.md §11).
"""

from __future__ import annotations

import contextvars
import logging
import uuid

from django.conf import settings
from django.http import HttpResponseNotFound
from django.shortcuts import redirect

_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")


def get_request_id() -> str:
    return _request_id.get()


def set_request_id(value: str) -> None:
    _request_id.set(value)


class RequestIDMiddleware:
    """Assign every request a correlation ID and echo it on the response."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        rid = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        set_request_id(rid)
        request.request_id = rid
        response = self.get_response(request)
        response["X-Request-ID"] = rid
        return response


class RequestIDLogFilter(logging.Filter):
    """Inject the current request ID into every log record (``%(request_id)s``)."""

    def filter(self, record):
        record.request_id = get_request_id()
        return True


class StaffAdminMiddleware:
    """Harden the admin path: staff must have confirmed TOTP MFA, and staff sessions
    expire faster than customer sessions (plan.md §11).

    An authenticated staff user without MFA is redirected to set it up rather than shown
    the admin. (The IP allow-list itself lives at Caddy, which 404s outsiders before the
    request reaches Django.)"""

    def __init__(self, get_response):
        self.get_response = get_response
        self.admin_prefix = "/" + settings.ADMIN_URL

    def __call__(self, request):
        if request.path.startswith(self.admin_prefix):
            user = getattr(request, "user", None)
            if user is not None and user.is_authenticated and user.is_staff:
                # Shorten this session for staff (idempotent; cheap).
                request.session.set_expiry(settings.STAFF_SESSION_AGE)
                if not self._has_mfa(user):
                    return self._deny(request)
        return self.get_response(request)

    @staticmethod
    def _has_mfa(user) -> bool:
        from allauth.mfa.models import Authenticator

        return Authenticator.objects.filter(user=user, type=Authenticator.Type.TOTP).exists()

    @staticmethod
    def _deny(request):
        # Superuser mid-setup gets redirected to configure TOTP; anyone else just 404s so
        # the admin's existence isn't confirmed to a half-authenticated session.
        mfa_url = f"{settings.FRONTEND_ORIGIN}/account/security"
        if request.user.is_superuser:
            return redirect(mfa_url)
        return HttpResponseNotFound()
