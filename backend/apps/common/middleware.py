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
        user = getattr(request, "user", None)
        is_staff = user is not None and user.is_authenticated and user.is_staff
        if is_staff:
            # Staff sessions expire faster on *every* path, not just admin — otherwise
            # a staff session browsing the storefront keeps the customer-length
            # lifetime (bugs.md #12). Idempotent; cheap.
            request.session.set_expiry(settings.STAFF_SESSION_AGE)
        if request.path.startswith(self.admin_prefix):
            # Django's native admin login authenticates with password only and skips
            # allauth's MFA step — never serve it (bugs.md #2). Staff log in via the
            # frontend (allauth headless login + MFA), then visit the admin.
            if request.path == self.admin_prefix + "login/":
                return redirect(f"{settings.FRONTEND_ORIGIN}/login")
            if is_staff and not self._session_used_mfa(request):
                return self._deny(request)
        return self.get_response(request)

    @staticmethod
    def _session_used_mfa(request) -> bool:
        """True only if *this session* completed an MFA step — enrollment alone isn't
        enough, since a session created without MFA (e.g. before enrollment, or via a
        non-allauth login path) would otherwise ride in on a phished password."""
        from allauth.account.authentication import get_authentication_records

        return any(r.get("method") == "mfa" for r in get_authentication_records(request))

    @staticmethod
    def _deny(request):
        # Superuser mid-setup gets redirected to configure TOTP; anyone else just 404s so
        # the admin's existence isn't confirmed to a half-authenticated session.
        mfa_url = f"{settings.FRONTEND_ORIGIN}/account/security"
        if request.user.is_superuser:
            return redirect(mfa_url)
        return HttpResponseNotFound()
