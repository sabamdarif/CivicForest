"""The staff "add a product" path: admin form → variant → gallery → live storefront.

This is the flow non-technical staff use to publish a new dress, so it gets one
end-to-end check: the whole chain (multi-file upload → ProductImage rows, the
size/colour vocabulary selects, is_active as the publish switch) breaks silently
otherwise — the form still renders, it just stops producing a buyable product.
"""

from __future__ import annotations

import io

import pytest
from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image
from rest_framework.test import APIClient

from apps.catalog import services
from apps.catalog.models import Color, Product, Size
from apps.common.factories import CategoryFactory, StaffUserFactory

pytestmark = pytest.mark.django_db

ADD_URL = f"/{settings.ADMIN_URL}catalog/product/add/"


def _png(name: str = "dress.png") -> SimpleUploadedFile:
    buf = io.BytesIO()
    Image.new("RGB", (40, 60), "#101010").save(buf, format="PNG")
    return SimpleUploadedFile(name, buf.getvalue(), content_type="image/png")


@pytest.fixture
def staff_client(settings):
    # Whitenoise's manifest storage needs collectstatic; the admin renders without it.
    settings.STORAGES = {
        **settings.STORAGES,
        "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
    }
    # DEBUG bypasses the per-session MFA gate (StaffAdminMiddleware), same as local dev.
    settings.DEBUG = True
    client = APIClient()
    client.force_login(StaffUserFactory(is_superuser=True))
    return client


def _form(category, **overrides) -> dict:
    """The POST an admin makes on the add-product page, inline formsets included."""
    data = {
        "name": "Midnight Wrap Dress",
        "slug": "midnight-wrap-dress",
        "category": str(category.pk),
        "base_price": "2499.00",
        "mrp": "",
        "hsn_code": "62044200",
        "country_of_origin": "India",
        "tax_rate": "5.00",
        "description": "Bias-cut wrap dress.",
        "material": "",
        "tags": [],
        "collections": [],
        "care_instructions": "",
        "fit_notes": "",
        "model_note": "",
        "gsm": "",
        "weight_grams": "",
        "length_cm": "",
        "width_cm": "",
        "height_cm": "",
        "meta_title": "",
        "meta_description": "",
        "is_active": "on",  # ← the publish switch
        "variants-TOTAL_FORMS": "1",
        "variants-INITIAL_FORMS": "0",
        "variants-MIN_NUM_FORMS": "0",
        "variants-MAX_NUM_FORMS": "1000",
        "variants-0-size": "M",
        "variants-0-color": "Black",
        "variants-0-color_hex": "",
        "variants-0-sku": "",
        "variants-0-price_override": "",
        "variants-0-stock_quantity": "4",
        "variants-0-is_active": "on",
        "images-TOTAL_FORMS": "0",
        "images-INITIAL_FORMS": "0",
        "images-MIN_NUM_FORMS": "0",
        "images-MAX_NUM_FORMS": "1000",
    }
    return {**data, **overrides}


def test_staff_publishes_a_dress_and_it_appears_on_the_storefront(staff_client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    category = CategoryFactory(name="Dresses", slug="dresses")
    # Size/colour are picked from the admin-managed vocabulary tables (migration-seeded).
    assert Size.objects.filter(name="M").exists() and Color.objects.filter(name="Black").exists()

    resp = staff_client.post(ADD_URL, _form(category, gallery=_png()), format="multipart")
    assert resp.status_code == 302, getattr(resp, "context_data", None)

    product = Product.objects.get(slug="midnight-wrap-dress")
    assert product.category == category
    assert product.is_active

    variant = product.variants.get()
    assert (variant.size, variant.color, variant.stock_quantity) == ("M", "Black", 4)
    assert variant.sku, "SKU is auto-generated when left blank"
    assert variant.color_hex == "#111111", "swatch filled in from the Color option"

    image = product.images.get()
    assert image.alt_text == product.name
    assert image.image.name.startswith("products/")
    assert sorted(image.width_variants) == ["40"], "srcset widths generated on upload"

    # The storefront reads through this queryset, so being in it is what "live" means.
    assert product in services.active_products()


def test_a_product_cannot_be_published_without_its_hsn_code(staff_client, settings, tmp_path):
    """C10 and L9 through the form staff actually use, not just through clean()."""
    settings.MEDIA_ROOT = tmp_path
    category = CategoryFactory(name="Dresses", slug="dresses")

    resp = staff_client.post(ADD_URL, _form(category, hsn_code=""), format="multipart")

    assert resp.status_code == 200  # form redisplayed with the error
    assert not Product.objects.filter(slug="midnight-wrap-dress").exists()


def test_gallery_rejects_a_file_that_is_not_an_image(staff_client, settings, tmp_path):
    settings.MEDIA_ROOT = tmp_path
    category = CategoryFactory(name="Dresses", slug="dresses")
    payload = SimpleUploadedFile("payload.png", b"<?php echo 1; ?>", content_type="image/png")

    resp = staff_client.post(ADD_URL, _form(category, gallery=payload), format="multipart")

    assert resp.status_code == 200  # form redisplayed with the error
    assert not Product.objects.filter(slug="midnight-wrap-dress").exists()


def test_admin_configuration_is_valid():
    """`manage.py check` catches admin misconfiguration (e.g. a list_display entry with
    no matching method) — pytest doesn't run it, so assert it here."""
    from django.core.management import call_command

    call_command("check", fail_level="WARNING")
