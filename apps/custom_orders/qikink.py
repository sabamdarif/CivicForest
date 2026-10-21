"""Qikink Open API client.

Auth: exchange ``ClientId`` + ``client_secret`` for an ``Accesstoken`` (cached in Redis
with a TTL), then send both as headers on every call. Base URL and paths are settings-
driven so they can be corrected against Qikink's live Postman reference without a code
change. All requests are pinned to the configured Qikink host (SSRF guard); credentials
live server-side only (plan.md §8).

The single low-level ``_send`` method is the only thing that touches the network, so
tests mock it and never hit Qikink."""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger("custom_orders")

_TOKEN_CACHE_KEY = "qikink:access_token"


class QikinkError(Exception):
    def __init__(self, message: str, code: str = "qikink_error"):
        super().__init__(message)
        self.message = message
        self.code = code


class QikinkClient:
    def __init__(self):
        self.base_url = settings.QIKINK_BASE_URL.rstrip("/")
        self.client_id = settings.QIKINK_CLIENT_ID
        self.client_secret = settings.QIKINK_CLIENT_SECRET

    # ─── low-level HTTP (the only network touch; mocked in tests) ─────────────
    def _send(
        self, method: str, path: str, *, headers=None, form=None, json_body=None, params=None
    ):
        url = f"{self.base_url}{path}"
        if params:
            url = f"{url}?{urllib.parse.urlencode(params)}"

        # SSRF guard: never allow the configured host to be swapped out by a path/param.
        if urllib.parse.urlparse(url).hostname != urllib.parse.urlparse(self.base_url).hostname:
            raise QikinkError("Refusing to call a non-Qikink host.", code="ssrf_blocked")

        data = None
        req_headers = dict(headers or {})
        if form is not None:
            data = urllib.parse.urlencode(form).encode()
            req_headers["Content-Type"] = "application/x-www-form-urlencoded"
        elif json_body is not None:
            data = json.dumps(json_body).encode()
            req_headers["Content-Type"] = "application/json"

        request = urllib.request.Request(url, data=data, headers=req_headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=20) as response:  # noqa: S310
                body = response.read().decode()
        except urllib.error.HTTPError as exc:  # pragma: no cover - network error path
            raise QikinkError(f"Qikink API error ({exc.code}).") from exc
        except urllib.error.URLError as exc:  # pragma: no cover - network error path
            raise QikinkError("Could not reach Qikink.") from exc
        return json.loads(body) if body else {}

    # ─── auth ────────────────────────────────────────────────────────────────
    def _token(self) -> str:
        cached = cache.get(_TOKEN_CACHE_KEY)
        if cached:
            return cached
        if not self.client_id or not self.client_secret:
            raise QikinkError("Qikink credentials are not configured.", code="not_configured")

        resp = self._send(
            "POST",
            settings.QIKINK_TOKEN_PATH,
            form={"ClientId": self.client_id, "client_secret": self.client_secret},
        )
        token = resp.get("Accesstoken") or resp.get("access_token")
        if not token:
            raise QikinkError("Qikink did not return an access token.")
        cache.set(_TOKEN_CACHE_KEY, token, settings.QIKINK_TOKEN_TTL)
        return token

    def _auth_headers(self) -> dict:
        return {"ClientId": self.client_id, "Accesstoken": self._token()}

    # ─── endpoints ───────────────────────────────────────────────────────────
    def create_order(self, payload: dict) -> dict:
        """Create a Qikink print+dropship order. Returns Qikink's response (order id)."""
        return self._send(
            "POST",
            settings.QIKINK_ORDER_CREATE_PATH,
            headers=self._auth_headers(),
            json_body=payload,
        )

    def get_order_status(self, qikink_order_id: str) -> dict:
        """Poll a Qikink order's status/tracking (Qikink has no outbound webhook)."""
        return self._send(
            "GET",
            settings.QIKINK_ORDER_STATUS_PATH,
            headers=self._auth_headers(),
            params={"id": qikink_order_id},
        )
