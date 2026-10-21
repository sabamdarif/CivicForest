"""Inventory (M8.8, O6): the view gate, the guarded adjustment endpoint, the ledger it writes,
and the refusal to drive stock below zero.

Stock is a money-adjacent path, so the adjustment earns adversarial tests: a role without the
stock permission cannot reach it, and an oversize removal is refused rather than clamped.
"""

import pytest
from django.contrib.auth.models import Permission
from django.http import StreamingHttpResponse
from django.urls import reverse

from apps.common.factories import ProductVariantFactory, StaffUserFactory, login_staff_with_mfa
from apps.common.models import StockAdjustment

pytestmark = pytest.mark.django_db


def _staff_with(client, *codenames):
    user = StaffUserFactory()
    for codename in codenames:
        user.user_permissions.add(Permission.objects.get(codename=codename))
    login_staff_with_mfa(client, user=user)
    return user


def test_list_requires_view_permission(client):
    _staff_with(client)
    assert client.get(reverse("backoffice:inventory")).status_code == 404


def test_list_shows_a_variant(client):
    ProductVariantFactory(sku="SKU-ABC")
    _staff_with(client, "view_productvariant")
    assert "SKU-ABC" in client.get(reverse("backoffice:inventory")).content.decode()


def test_adjust_rejects_role_without_stock_permission(client):
    variant = ProductVariantFactory(stock_quantity=5)
    _staff_with(client, "view_productvariant")  # can look, cannot adjust

    response = client.post(
        reverse("backoffice:inventory_adjust", kwargs={"pk": variant.pk}),
        {"delta": "3", "reason": "received"},
    )

    assert response.status_code == 404
    variant.refresh_from_db()
    assert variant.stock_quantity == 5
    assert not StockAdjustment.objects.exists()


def test_adjust_applies_delta_and_records_the_reason(client):
    variant = ProductVariantFactory(stock_quantity=5)
    _staff_with(client, "add_stockadjustment")

    client.post(
        reverse("backoffice:inventory_adjust", kwargs={"pk": variant.pk}),
        {"delta": "3", "reason": "received", "note": "New carton"},
    )

    variant.refresh_from_db()
    assert variant.stock_quantity == 8
    row = StockAdjustment.objects.get(variant=variant)
    assert (row.delta, row.resulting_quantity, row.reason) == (3, 8, "received")


def test_adjust_refuses_to_go_below_zero(client):
    variant = ProductVariantFactory(stock_quantity=2)
    _staff_with(client, "add_stockadjustment")

    client.post(
        reverse("backoffice:inventory_adjust", kwargs={"pk": variant.pk}),
        {"delta": "-5", "reason": "damaged"},
    )

    variant.refresh_from_db()
    assert variant.stock_quantity == 2
    assert not StockAdjustment.objects.exists()


def test_low_stock_filter_and_per_variant_threshold(client):
    ProductVariantFactory(sku="HEALTHY", stock_quantity=100)
    # Above the store default of 5, but its own threshold is higher, so it is low.
    ProductVariantFactory(sku="CUSTOM", stock_quantity=8, low_stock_threshold=10)
    _staff_with(client, "view_productvariant")

    body = client.get(reverse("backoffice:inventory"), {"low": "1"}).content.decode()

    assert "CUSTOM" in body
    assert "HEALTHY" not in body


def test_export_streams_with_header(client):
    ProductVariantFactory()
    _staff_with(client, "view_productvariant")

    response = client.get(reverse("backoffice:inventory"), {"export": "csv"})

    assert isinstance(response, StreamingHttpResponse)
    assert next(iter(response.streaming_content)).decode().startswith("sku,")
