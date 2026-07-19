"""Razorpay gateway wrapper.

Signature verification is pure HMAC-SHA256, so it needs no SDK and no network — this
is the security-critical part and is fully unit-testable. The one outbound call (create
an order, server-to-server) uses the stdlib so we add no dependency; tests mock
``create_order`` rather than hitting the network (plan.md §9, §15)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import urllib.error
import urllib.request
from decimal import Decimal

from django.conf import settings

RAZORPAY_ORDERS_URL = "https://api.razorpay.com/v1/orders"


class PaymentError(Exception):
    def __init__(self, message: str, code: str = "payment_error"):
        super().__init__(message)
        self.message = message
        self.code = code


def to_paise(amount: Decimal) -> int:
    """Razorpay works in the smallest currency unit (paise for INR)."""
    return int((amount * 100).to_integral_value())


def _sign(secret: str, message: bytes) -> str:
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()


def create_order(
    amount: Decimal, *, currency: str, receipt: str, notes: dict | None = None
) -> dict:
    """Create a Razorpay order server-to-server and return its JSON (with ``id``).

    Raises ``PaymentError`` if credentials are missing or the API call fails — the
    caller surfaces that as a clean error rather than a 500."""
    if not settings.RAZORPAY_KEY_ID or not settings.RAZORPAY_KEY_SECRET:
        raise PaymentError("Payments are not configured.", code="not_configured")

    # E2E/offline fake (settings.e2e only): skip the network call so the rest of the
    # money path — order, webhook, fulfilment — can run against the real code.
    if getattr(settings, "RAZORPAY_FAKE_MODE", False):
        return {"id": f"order_fake_{receipt}", "status": "created"}

    payload = json.dumps(
        {
            "amount": to_paise(amount),
            "currency": currency,
            "receipt": receipt,
            "notes": notes or {},
            "payment_capture": 1,
        }
    ).encode()

    creds = base64.b64encode(
        f"{settings.RAZORPAY_KEY_ID}:{settings.RAZORPAY_KEY_SECRET}".encode()
    ).decode()
    request = urllib.request.Request(
        RAZORPAY_ORDERS_URL,
        data=payload,
        headers={"Authorization": f"Basic {creds}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310
            return json.loads(response.read().decode())
    except urllib.error.HTTPError as exc:  # pragma: no cover - network error path
        raise PaymentError(f"Razorpay rejected the order ({exc.code}).") from exc
    except urllib.error.URLError as exc:  # pragma: no cover - network error path
        raise PaymentError("Could not reach the payment gateway.") from exc


def verify_payment_signature(order_id: str, payment_id: str, signature: str) -> bool:
    """Verify the client-side checkout callback signature. Advisory only — the webhook
    is the source of truth for 'paid' (plan.md §9)."""
    expected = _sign(settings.RAZORPAY_KEY_SECRET, f"{order_id}|{payment_id}".encode())
    return hmac.compare_digest(expected, signature or "")


def verify_webhook_signature(raw_body: bytes, signature: str) -> bool:
    """Verify a webhook against the **raw request body** using the separate webhook
    secret. Verifying the raw bytes (not a re-serialised object) is essential — any
    re-encoding would change the bytes and break the check (plan.md §9)."""
    if not settings.RAZORPAY_WEBHOOK_SECRET:
        return False
    expected = _sign(settings.RAZORPAY_WEBHOOK_SECRET, raw_body)
    return hmac.compare_digest(expected, signature or "")
