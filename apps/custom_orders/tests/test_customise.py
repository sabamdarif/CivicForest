"""Add-to-cart for the custom line (M7.5, M7.11).

The surcharge and the rights wording are the server's: the client sends a size, not a price,
and must actively accept the rights acknowledgement. These tests pin that boundary."""

from decimal import Decimal

import pytest
from rest_framework.test import APIClient

from apps.cart.models import CartItem
from apps.custom_orders.models import CustomBlank, CustomDesignOrder, DesignUpload

pytestmark = pytest.mark.django_db


def _blank(variant):
    return CustomBlank.objects.create(
        product=variant.product,
        slug="custom-tee",
        print_type_id=1,
        print_areas={"front": {"placement_sku": "fr", "max_width_in": 12, "max_height_in": 16}},
        surcharge_tiers=[
            {"max_width_in": 6, "max_height_in": 6, "surcharge": "0.00"},
            {"max_width_in": 12, "max_height_in": 16, "surcharge": "199.00"},
        ],
    )


def _ready_design(user):
    return DesignUpload.objects.create(
        user=user,
        r2_key_print="designs/print/abc.png",
        status=DesignUpload.Status.READY,
        review_status=DesignUpload.ReviewStatus.AUTO_OK,
        width_px=2000,
        height_px=2000,
    )


def _payload(design, **overrides):
    data = {
        "blank_slug": "custom-tee",
        "design_id": str(design.id),
        "size": "M",
        "color": "White",
        "placement_sku": "fr",
        "width_inches": "10.00",
        "height_inches": "12.00",
        "quantity": 1,
        "rights_accepted": True,
    }
    data.update(overrides)
    return data


def test_add_to_cart_creates_line_with_server_surcharge_and_rights(variant, user, settings):
    _blank(variant)
    design = _ready_design(user)
    client = APIClient()
    client.force_authenticate(user)

    resp = client.post("/api/v1/designs/add-to-cart/", _payload(design), format="json")
    assert resp.status_code == 201, resp.data

    custom = CustomDesignOrder.objects.get(id=resp.data["id"])
    assert custom.print_surcharge == Decimal("199.00")
    assert custom.rights_ack_text == settings.CUSTOM_RIGHTS_TEXT
    assert custom.blank_variant_id == variant.id
    item = CartItem.objects.get(custom_design=custom)
    assert item.variant_id == variant.id and item.quantity == 1


def test_add_to_cart_requires_rights_acceptance(variant, user):
    _blank(variant)
    design = _ready_design(user)
    client = APIClient()
    client.force_authenticate(user)

    resp = client.post(
        "/api/v1/designs/add-to-cart/", _payload(design, rights_accepted=False), format="json"
    )
    assert resp.status_code == 400
    assert not CartItem.objects.exists()


def test_add_to_cart_rejects_another_users_design(variant, user, django_user_model):
    _blank(variant)
    other = django_user_model.objects.create_user(email="e@example.com", password="pw-1234567!")
    design = _ready_design(other)
    client = APIClient()
    client.force_authenticate(user)

    resp = client.post("/api/v1/designs/add-to-cart/", _payload(design), format="json")
    assert resp.status_code == 404
    assert not CartItem.objects.exists()


def test_add_to_cart_rejects_unsanitised_design(variant, user):
    _blank(variant)
    design = DesignUpload.objects.create(user=user, status=DesignUpload.Status.UPLOADING)
    client = APIClient()
    client.force_authenticate(user)

    resp = client.post("/api/v1/designs/add-to-cart/", _payload(design), format="json")
    assert resp.status_code == 400
    assert not CartItem.objects.exists()
