import hashlib
import hmac
import json
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from apps.catalog.models import Category, Product, ProductVariant

User = get_user_model()

WEBHOOK_SECRET = "whsec_test_secret"


@pytest.fixture
def user(db):
    return User.objects.create_user(email="buyer@example.com", password="pw-1234567!")


@pytest.fixture
def variant(db):
    category = Category.objects.create(name="T-Shirts", slug="t-shirts")
    product = Product.objects.create(
        name="Classic Black Tee",
        slug="classic-black-tee",
        category=category,
        base_price=Decimal("800.00"),
    )
    return ProductVariant.objects.create(
        product=product, size="M", color="Black", sku="CBT-BLACK-M", stock_quantity=3
    )


def sign_body(raw: bytes, secret: str = WEBHOOK_SECRET) -> str:
    return hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def capture_event(
    gateway_order_id: str, payment_id: str = "pay_TEST", event_id: str = "evt_1"
) -> bytes:
    return json.dumps(
        {
            "id": event_id,
            "event": "payment.captured",
            "payload": {"payment": {"entity": {"id": payment_id, "order_id": gateway_order_id}}},
        }
    ).encode()
