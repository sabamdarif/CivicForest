"""Payment endpoints.

- ``/payments/verify`` — the browser posts the Razorpay callback here. Advisory only.
- ``/payments/webhook/razorpay`` — the authoritative server-to-server webhook. Verified
  against the **raw body**, deduped by event id, no auth/CSRF (it's machine-to-machine),
  and the only path that fulfils an order (plan.md §9)."""

from __future__ import annotations

import json
import logging

from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from . import gateway, services

logger = logging.getLogger("payments")


class PaymentVerifyView(APIView):
    """Advisory callback from Razorpay's browser checkout. Confirms the signature for
    UI feedback but never fulfils — the webhook is the source of truth."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        order_id = request.data.get("razorpay_order_id", "")
        payment_id = request.data.get("razorpay_payment_id", "")
        signature = request.data.get("razorpay_signature", "")
        ok = services.verify_callback(order_id, payment_id, signature)
        if not ok:
            return Response({"verified": False}, status=status.HTTP_404_NOT_FOUND)
        return Response({"verified": True}, status=status.HTTP_200_OK)


class RazorpayWebhookView(APIView):
    """Server-to-server webhook. No session auth (so no CSRF); trust is established by
    the HMAC signature over the raw body, not by a cookie."""

    permission_classes = [AllowAny]
    authentication_classes = []  # machine-to-machine; bypasses SessionAuthentication/CSRF

    def post(self, request):
        raw_body = request.body  # raw bytes — must verify against these, not re-encoded JSON
        signature = request.headers.get("X-Razorpay-Signature", "")
        if not gateway.verify_webhook_signature(raw_body, signature):
            logger.warning("Rejected Razorpay webhook with bad signature")
            return Response({"detail": "invalid signature"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            event = json.loads(raw_body.decode() or "{}")
        except (ValueError, UnicodeDecodeError):
            return Response({"detail": "invalid payload"}, status=status.HTTP_400_BAD_REQUEST)

        result = services.process_webhook(raw_body, signature, event)
        logger.info("Razorpay webhook %s → %s", event.get("event"), result)
        if result == "unknown_order":
            # Payment row not committed yet, so 5xx and Razorpay retries.
            return Response({"status": result}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({"status": result}, status=status.HTTP_200_OK)
