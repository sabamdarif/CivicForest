from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.catalog.models import Category, Product, ProductVariant

User = get_user_model()


@pytest.fixture
def user(db):
    return User.objects.create_user(email="buyer@example.com", password="pw-1234567!")


@pytest.fixture
def other_user(db):
    return User.objects.create_user(email="someone@example.com", password="pw-7654321!")


@pytest.fixture
def auth_client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def category(db):
    return Category.objects.create(name="T-Shirts", slug="t-shirts")


@pytest.fixture
def variant(db, category):
    product = Product.objects.create(
        name="Classic Black Tee",
        slug="classic-black-tee",
        category=category,
        base_price=Decimal("800.00"),
    )
    return ProductVariant.objects.create(
        product=product, size="M", color="Black", sku="CBT-BLACK-M", stock_quantity=3
    )


SHIPPING = {
    "full_name": "Test Buyer",
    "phone": "9999999999",
    "line1": "1 MG Road",
    "city": "Bengaluru",
    "state": "Karnataka",
    "postal_code": "560001",
    "country": "IN",
}
