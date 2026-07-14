import io
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from PIL import Image

from apps.catalog.models import Category, Product, ProductVariant
from apps.orders.models import Order

User = get_user_model()


def make_png_bytes(size=(64, 64), color=(200, 40, 40), *, with_exif=False) -> bytes:
    img = Image.new("RGB", size, color)
    out = io.BytesIO()
    if with_exif:
        exif = img.getexif()
        exif[0x010F] = "SecretCameraMaker"  # Make tag — should NOT survive re-encode
        img.save(out, format="JPEG", exif=exif)
    else:
        img.save(out, format="PNG")
    return out.getvalue()


@pytest.fixture(autouse=True)
def _tmp_media(settings, tmp_path):
    """Keep design uploads out of the real ``mediafiles/`` dir during tests."""
    settings.MEDIA_ROOT = str(tmp_path)


@pytest.fixture
def user(db):
    return User.objects.create_user(email="buyer@example.com", password="pw-1234567!")


@pytest.fixture
def variant(db):
    category = Category.objects.create(name="T-Shirts", slug="t-shirts")
    product = Product.objects.create(
        name="Custom Tee", slug="custom-tee", category=category, base_price=Decimal("999.00")
    )
    return ProductVariant.objects.create(
        product=product, size="M", color="White", sku="CUS-WH-M", stock_quantity=100
    )


@pytest.fixture
def paid_order(db, user):
    return Order.objects.create(
        user=user,
        status=Order.Status.PAID,
        email=user.email,
        phone="9999999999",
        ship_full_name="Test Buyer",
        ship_line1="1 MG Road",
        ship_city="Bengaluru",
        ship_state="Karnataka",
        ship_postal_code="560001",
        ship_country="IN",
        subtotal=Decimal("999.00"),
        total=Decimal("999.00"),
    )
