"""Request/correlation-ID plumbing, staff admin hardening and the response CSP.

One request ID is generated (or taken from an inbound ``X-Request-ID``) per request,
stashed on a contextvar so every log record carries it, and echoed back on the response,
so a single failed checkout can be traced end to end. ``StaffAdminMiddleware`` gates the
admin path on confirmed TOTP MFA and shortens staff sessions.
``ContentSecurityPolicyMiddleware`` sets one strict policy whose ``script-src`` forbids
inline script (every script this site serves is an external file).
"""

from __future__ import annotations

import contextvars
import logging
import re
import uuid
from urllib.parse import urlsplit

from django.conf import settings
from django.http import HttpResponseNotFound
from django.shortcuts import redirect

_request_id: contextvars.ContextVar[str] = contextvars.ContextVar("request_id", default="-")
_VALID_REQUEST_ID = re.compile(r"^[A-Za-z0-9-]{1,64}$")


def get_request_id() -> str:
    return _request_id.get()


def set_request_id(value: str) -> None:
    _request_id.set(value)


def session_completed_mfa(request) -> bool:
    """True only if *this session* completed an MFA step.

    Enrollment alone isn't enough: a session created without MFA (before enrollment, or via a
    non-allauth login path) would otherwise ride in on a phished password. The staff admin gate
    and the back-office ``StaffRequiredMixin`` both hang off this one rule."""
    from allauth.account.authentication import get_authentication_records

    return any(r.get("method") == "mfa" for r in get_authentication_records(request))


class RequestIDMiddleware:
    """Assign every request a correlation ID and echo it on the response."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        incoming = request.headers.get("X-Request-ID", "")
        rid = incoming if _VALID_REQUEST_ID.fullmatch(incoming) else uuid.uuid4().hex
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


class MaintenanceMiddleware:
    """Serve a branded 503 for everyone while ``MAINTENANCE_MODE`` is on (M9.12).

    healthz, the admin and the back-office are exempt, so an uptime monitor still gets its 200
    and staff can keep working through the outage. The page is rendered without a database read,
    because a dead database is a reason to be in maintenance in the first place."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.exempt = ("/healthz/", "/" + settings.ADMIN_URL, "/" + settings.BACKOFFICE_URL)

    def __call__(self, request):
        if settings.MAINTENANCE_MODE and not request.path.startswith(self.exempt):
            from django.shortcuts import render

            return render(request, "errors/maintenance.html", status=503)
        return self.get_response(request)


class StaffAdminMiddleware:
    """Harden the admin path: staff must have confirmed TOTP MFA, and staff sessions
    expire faster than customer sessions.

    A staff user whose session never completed an MFA step gets a 404, so the admin's
    existence is not confirmed to a half-authenticated session. A superuser mid-setup is
    sent to the login flow instead."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.admin_prefix = "/" + settings.ADMIN_URL

    def __call__(self, request):
        user = getattr(request, "user", None)
        is_staff = user is not None and user.is_authenticated and user.is_staff
        if is_staff:
            # Staff sessions expire faster on *every* path, not just admin, otherwise a
            # staff session browsing the storefront keeps the customer-length lifetime.
            request.session.set_expiry(settings.STAFF_SESSION_AGE)
        if request.path.startswith(self.admin_prefix):
            # Django's native admin login authenticates with a password only and skips
            # allauth's MFA step, so it is never served. Staff sign in through the site.
            if request.path == self.admin_prefix + "login/":
                return redirect(settings.LOGIN_URL)
            if is_staff and not self._session_used_mfa(request):
                return self._deny(request)
        return self.get_response(request)

    @staticmethod
    def _session_used_mfa(request) -> bool:
        return session_completed_mfa(request)

    @staticmethod
    def _deny(request):
        # Superuser mid-setup gets sent to the login flow to complete MFA; anyone else
        # just 404s, so the admin's existence isn't confirmed to a half-authenticated
        # session.
        if request.user.is_superuser:
            return redirect(settings.LOGIN_URL)
        return HttpResponseNotFound()


def _origin(url: str) -> str | None:
    """The ``scheme://host`` of a configured URL, or None when it is unset. R2 and the
    gateway come from env, so the policy allowlists their real origin without hardcoding it."""
    if not url:
        return None
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else None


class ContentSecurityPolicyMiddleware:
    """Set the response CSP (M10.5). ``script-src`` has no ``'unsafe-inline'``: every script
    the site serves is an external file, so inline injection cannot execute. ``style-src``
    keeps ``'unsafe-inline'`` because dynamic ``style=`` attributes (swatch colours, meters)
    are not an XSS vector worth a template-wide refactor. GA hosts are added only when
    analytics is configured; the gateway and R2 origins come from settings."""

    def __init__(self, get_response):
        self.get_response = get_response
        self.policy = self._build()

    @staticmethod
    def _build() -> str:
        gateway = "https://checkout.razorpay.com"
        r2_public = _origin(getattr(settings, "R2_PUBLIC_BASE_URL", ""))
        r2_endpoint = _origin(getattr(settings, "S3_ENDPOINT_URL", ""))
        ga = ["https://www.googletagmanager.com", "https://www.google-analytics.com"]
        analytics_on = bool(getattr(settings, "GOOGLE_ANALYTICS_ID", ""))

        script = ["'self'", gateway]
        img = ["'self'", "data:"]
        connect = ["'self'"]
        if analytics_on:
            script.append("https://www.googletagmanager.com")
            img += ga
            connect += ga
        if r2_public:
            img.append(r2_public)
        if r2_endpoint:
            connect.append(r2_endpoint)

        directives = {
            "default-src": ["'self'"],
            "script-src": script,
            "style-src": ["'self'", "'unsafe-inline'"],
            "img-src": img,
            "font-src": ["'self'"],
            "connect-src": connect,
            "frame-src": [gateway],
            "form-action": ["'self'"],
            "base-uri": ["'self'"],
            "object-src": ["'none'"],
            "frame-ancestors": ["'none'"],
        }
        return "; ".join(f"{name} {' '.join(values)}" for name, values in directives.items())

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("Content-Security-Policy", self.policy)
        return response
