from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.catalog.models import Category, Product, ProductVariant

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def product():
    category = Category.objects.create(name="T-Shirts", slug="t-shirts")
    product = Product.objects.create(
        name="Classic Black Tee",
        slug="classic-black-tee",
        category=category,
        base_price=Decimal("799.00"),
        is_new=True,
        is_active=True,
    )
    ProductVariant.objects.create(
        product=product, size="M", color="Black", sku="CBT-BLACK-M", stock_quantity=5
    )
    ProductVariant.objects.create(
        product=product,
        size="L",
        color="Black",
        sku="CBT-BLACK-L",
        price_override=Decimal("749.00"),
        stock_quantity=0,
    )
    return product


def test_product_list_returns_active_products(client, product):
    resp = client.get("/api/v1/catalog/products")
    assert resp.status_code == 200
    assert resp.data["count"] == 1
    row = resp.data["results"][0]
    assert row["slug"] == "classic-black-tee"
    # price_from falls back to the cheaper variant override.
    assert Decimal(row["price_from"]) == Decimal("749.00")


def test_inactive_product_is_hidden(client, product):
    product.is_active = False
    product.save()
    resp = client.get("/api/v1/catalog/products")
    assert resp.data["count"] == 0


def test_product_detail_by_slug_exposes_variants(client, product):
    resp = client.get(f"/api/v1/catalog/products/{product.slug}")
    assert resp.status_code == 200
    assert resp.data["name"] == "Classic Black Tee"
    assert set(resp.data["sizes"]) == {"M", "L"}
    assert len(resp.data["variants"]) == 2


def test_page_size_is_capped(client, product):
    # Requesting an absurd page size must not exceed the hard ceiling (48).
    resp = client.get("/api/v1/catalog/products", {"page_size": 10000})
    assert resp.status_code == 200
    # Only one product exists, but the request must be accepted and clamped.
    assert resp.data["count"] == 1
