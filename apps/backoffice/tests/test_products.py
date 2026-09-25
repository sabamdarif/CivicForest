"""Product management (M8.7): the view gates, the guarded bulk/duplicate/archive endpoints, the
CSV round-trip and its dry-run, and the variant matrix save.

Authz paths earn adversarial tests: a view-only role reaches none of the mutating endpoints, a
tampered id in a bulk post changes nothing, and the import preview writes nothing until confirmed.
"""

import uuid

import pytest
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import StreamingHttpResponse
from django.urls import reverse

from apps.catalog.models import Product
from apps.catalog.services import PRODUCT_CSV_HEADER
from apps.common.factories import (
    CategoryFactory,
    ProductFactory,
    ProductVariantFactory,
    StaffUserFactory,
    login_staff_with_mfa,
)

pytestmark = pytest.mark.django_db


def _staff_with(client, *codenames):
    """A gated staff user (not a superuser) holding exactly the named catalog permissions."""
    user = StaffUserFactory()
    for codename in codenames:
        user.user_permissions.add(Permission.objects.get(codename=codename))
    login_staff_with_mfa(client, user=user)
    return user


def _product_fields(product) -> dict:
    return {
        "name": product.name,
        "slug": product.slug,
        "category": str(product.category_id),
        "base_price": "800.00",
        "mrp": "",
        "description": "",
        "material": "",
        "tags": [],
        "collections": [],
        "country_of_origin": "India",
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
        "is_active": "on",
    }


def _empty_formsets() -> dict:
    return {
        "variants-TOTAL_FORMS": "0",
        "variants-INITIAL_FORMS": "0",
        "variants-MIN_NUM_FORMS": "0",
        "variants-MAX_NUM_FORMS": "1000",
        "images-TOTAL_FORMS": "0",
        "images-INITIAL_FORMS": "0",
        "images-MIN_NUM_FORMS": "0",
        "images-MAX_NUM_FORMS": "1000",
    }


# ── Access ──────────────────────────────────────────────────────────────────
def test_list_requires_view_permission(client):
    _staff_with(client)  # staff + MFA, no catalog permission
    assert client.get(reverse("backoffice:products")).status_code == 404


def test_list_shows_a_product(client):
    product = ProductFactory(name="Linen Shirt")
    _staff_with(client, "view_product")
    assert product.name in client.get(reverse("backoffice:products")).content.decode()


def test_edit_form_needs_change_permission(client):
    product = ProductFactory()
    _staff_with(client, "view_product")  # can view the list, not the form
    assert (
        client.get(reverse("backoffice:product_edit", kwargs={"pk": product.pk})).status_code == 404
    )


def test_create_form_needs_add_permission(client):
    _staff_with(client, "view_product")
    assert client.get(reverse("backoffice:product_new")).status_code == 404


def test_import_page_needs_permission(client):
    _staff_with(client, "view_product")
    assert client.get(reverse("backoffice:product_import")).status_code == 404


# ── Bulk inline editing ───────────────────────────────────────────────────────
def test_bulk_rejects_view_only_role(client):
    product = ProductFactory(base_price="800.00", is_active=True)
    _staff_with(client, "view_product")  # no change_product

    response = client.post(
        reverse("backoffice:product_bulk"),
        {"ids": [str(product.id)], f"price-{product.id}": "999.00", f"active-{product.id}": "on"},
    )

    assert response.status_code == 404
    product.refresh_from_db()
    assert product.base_price == pytest.approx(800.00)


def test_bulk_updates_price_and_active(client):
    product = ProductFactory(base_price="800.00", is_active=True)
    _staff_with(client, "change_product")

    client.post(
        reverse("backoffice:product_bulk"),
        {"ids": [str(product.id)], f"price-{product.id}": "999.00"},  # active omitted → unticked
    )

    product.refresh_from_db()
    assert product.base_price == pytest.approx(999.00)
    assert product.is_active is False


def test_bulk_drops_a_tampered_id(client):
    _staff_with(client, "change_product")
    response = client.post(
        reverse("backoffice:product_bulk"),
        {"ids": ["not-a-uuid", str(uuid.uuid4())], "price-not-a-uuid": "10.00"},
    )
    assert response.status_code == 302


# ── Duplicate and archive ───────────────────────────────────────────────────────
def test_duplicate_needs_add_permission(client):
    product = ProductFactory()
    _staff_with(client, "change_product")  # can archive, cannot add
    response = client.post(
        reverse("backoffice:product_action", kwargs={"pk": product.pk}), {"action": "duplicate"}
    )
    assert response.status_code == 404


def test_duplicate_clones_as_inactive_draft(client):
    product = ProductFactory(slug="tee", is_active=True)
    ProductVariantFactory(product=product, size="M", color="Black", stock_quantity=4)
    _staff_with(client, "add_product")

    client.post(
        reverse("backoffice:product_action", kwargs={"pk": product.pk}), {"action": "duplicate"}
    )

    clone = Product.objects.exclude(pk=product.pk).get(slug="tee-copy")
    assert clone.is_active is False
    assert clone.variants.count() == 1


def test_archive_hides_without_deleting(client):
    product = ProductFactory(is_active=True)
    _staff_with(client, "change_product")

    client.post(
        reverse("backoffice:product_action", kwargs={"pk": product.pk}), {"action": "archive"}
    )

    product.refresh_from_db()
    assert product.is_active is False
    assert Product.objects.filter(pk=product.pk).exists()


# ── Variant matrix ──────────────────────────────────────────────────────────────
def test_variant_matrix_adds_a_variant(client):
    product = ProductFactory()
    _staff_with(client, "change_product")
    payload = {
        **_product_fields(product),
        **_empty_formsets(),
        "variants-TOTAL_FORMS": "1",
        "variants-0-size": "M",
        "variants-0-color": "Black",
        "variants-0-color_hex": "",
        "variants-0-sku": "",
        "variants-0-price_override": "",
        "variants-0-stock_quantity": "7",
        "variants-0-is_active": "on",
    }

    response = client.post(reverse("backoffice:product_edit", kwargs={"pk": product.pk}), payload)

    assert response.status_code == 302, response.content
    variant = product.variants.get()
    assert (variant.size, variant.color, variant.stock_quantity) == ("M", "Black", 7)


# ── CSV import and export ───────────────────────────────────────────────────────
def _csv(*rows) -> str:
    return ",".join(PRODUCT_CSV_HEADER) + "\n" + "".join(row + "\n" for row in rows)


def test_export_streams_with_header(client):
    ProductFactory()
    _staff_with(client, "add_product", "change_product")

    response = client.get(reverse("backoffice:product_import"), {"export": "csv"})

    assert isinstance(response, StreamingHttpResponse)
    assert next(iter(response.streaming_content)).decode().startswith("slug,")


def test_import_preview_writes_nothing(client):
    CategoryFactory(slug="tees")
    _staff_with(client, "add_product", "change_product")
    text = _csv("new-tee,New Tee,tees,,999,,India,true,false,false")
    before = Product.objects.count()

    response = client.post(
        reverse("backoffice:product_import"),
        {"file": SimpleUploadedFile("p.csv", text.encode(), content_type="text/csv")},
    )

    assert response.status_code == 200
    assert "create" in response.content.decode()
    assert Product.objects.count() == before


def test_import_confirm_creates_the_product(client):
    CategoryFactory(slug="tees")
    _staff_with(client, "add_product", "change_product")
    text = _csv("new-tee,New Tee,tees,,999,,India,true,false,false")

    client.post(reverse("backoffice:product_import"), {"step": "confirm", "csv": text})

    product = Product.objects.get(slug="new-tee")
    assert product.name == "New Tee"
    assert product.base_price == pytest.approx(999)
