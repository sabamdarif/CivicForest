"""The customise landing and design-tool pages render (M7.4, M7.5)."""

import pytest
from django.test import Client

from apps.custom_orders.models import CustomBlank

pytestmark = pytest.mark.django_db


def _blank(variant):
    return CustomBlank.objects.create(
        product=variant.product,
        slug="custom-tee",
        tagline="Your art on a tee.",
        print_areas={
            "front": {
                "placement_sku": "fr",
                "max_width_in": 12,
                "max_height_in": 16,
                "px": {"x": 120, "y": 90, "w": 260, "h": 340},
            }
        },
        surcharge_tiers=[{"max_width_in": 12, "max_height_in": 16, "surcharge": "199.00"}],
    )


def test_landing_lists_blanks(variant):
    _blank(variant)
    resp = Client().get("/customise/")
    assert resp.status_code == 200
    assert b"Custom Tee" in resp.content


def test_designer_page_renders_for_guest(variant):
    _blank(variant)
    resp = Client().get("/customise/custom-tee/")
    assert resp.status_code == 200
    assert b"data-designer" in resp.content
    assert b"designer.js" in resp.content


def test_designer_404_for_unknown_blank():
    assert Client().get("/customise/nope/").status_code == 404
