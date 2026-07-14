from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.catalog.models import Category, Product, ProductVariant


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def category(db):
    return Category.objects.create(name="T-Shirts", slug="t-shirts")


@pytest.fixture
def product(db, category):
    product = Product.objects.create(
        name="Classic Black Tee",
        slug="classic-black-tee",
        category=category,
        base_price=Decimal("800.00"),
        is_active=True,
    )
    ProductVariant.objects.create(
        product=product, size="M", color="Black", sku="CBT-BLACK-M", stock_quantity=5
    )
    return product


@pytest.fixture
def variant(product):
    return product.variants.get(sku="CBT-BLACK-M")
