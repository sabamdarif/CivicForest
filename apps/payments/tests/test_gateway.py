import pytest
from django.test import override_settings

from apps.payments import gateway

pytestmark = pytest.mark.django_db


@override_settings(RAZORPAY_KEY_SECRET="rzp_secret")
def test_payment_signature_valid():
    # Razorpay signs "order_id|payment_id" with the API secret.
    import hashlib
    import hmac

    body = b"order_1|pay_1"
    sig = hmac.new(b"rzp_secret", body, hashlib.sha256).hexdigest()
    assert gateway.verify_payment_signature("order_1", "pay_1", sig) is True


@override_settings(RAZORPAY_KEY_SECRET="rzp_secret")
def test_payment_signature_invalid():
    assert gateway.verify_payment_signature("order_1", "pay_1", "deadbeef") is False


@override_settings(RAZORPAY_WEBHOOK_SECRET="whsec_test_secret")
def test_webhook_signature_checks_raw_body():
    from .conftest import capture_event, sign_body

    raw = capture_event("order_x", amount_paise=100)
    assert gateway.verify_webhook_signature(raw, sign_body(raw)) is True
    # A single flipped byte breaks it.
    assert gateway.verify_webhook_signature(raw + b" ", sign_body(raw)) is False


@override_settings(RAZORPAY_WEBHOOK_SECRET="")
def test_webhook_rejects_when_secret_unset():
    assert gateway.verify_webhook_signature(b"{}", "anything") is False


def test_to_paise_rounds_to_integer_minor_units():
    from decimal import Decimal

    assert gateway.to_paise(Decimal("1600.00")) == 160000
    assert gateway.to_paise(Decimal("59.50")) == 5950
