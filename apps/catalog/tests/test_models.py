"""The catalogue's two guards: the HSN code a live product needs, and a hex that cannot
carry CSS.

Both exist because the alternative fails outside the code. A product missing its HSN code
is a GST invoice that cannot be issued, and an unvalidated swatch hex is a style attribute
written straight into every page that lists the product.
"""

import pytest
from django.core.exceptions import ValidationError

from apps.catalog.models import Category, Collection, Color, Product, ProductVariant

pytestmark = pytest.mark.django_db


@pytest.fixture
def category():
    return Category.objects.create(name="Hoodies", slug="hoodies")


def _product(category, **kwargs):
    return Product(
        name="Signature Hoodie",
        slug="signature-hoodie",
        category=category,
        base_price="1199.00",
        **kwargs,
    )


def test_a_live_product_needs_its_hsn_code(category):
    with pytest.raises(ValidationError) as exc:
        _product(category, is_active=True, hsn_code="").full_clean()

    assert "hsn_code" in exc.value.message_dict


def test_a_draft_product_may_still_be_missing_it(category):
    # Staff have to be able to save a half-filled product; the gate is on going live.
    _product(category, is_active=False, hsn_code="").full_clean()


def test_country_of_origin_is_never_blank(category):
    # No clean() gate needed: the field has a default and the form requires it.
    with pytest.raises(ValidationError) as exc:
        _product(category, hsn_code="61091000", country_of_origin="").full_clean()

    assert "country_of_origin" in exc.value.message_dict


def test_a_complete_live_product_passes(category):
    _product(category, is_active=True, hsn_code="61091000").full_clean()


def test_the_hsn_code_has_to_look_like_one(category):
    with pytest.raises(ValidationError) as exc:
        _product(category, hsn_code="61-09").full_clean()

    assert "hsn_code" in exc.value.message_dict


@pytest.mark.parametrize("bad", ["red", "#12", "#1f3d2b; background:url(//evil)", "1f3d2b"])
def test_a_swatch_hex_cannot_carry_anything_but_a_hex(bad):
    with pytest.raises(ValidationError):
        Color(name="Suspicious", hex=bad).full_clean()


@pytest.mark.parametrize("good", ["#fff", "#1f3d2b", ""])
def test_a_real_hex_or_none_at_all_is_accepted(good):
    Color(name="Forest", hex=good).full_clean()


def test_the_variant_swatch_is_validated_too(category):
    # color_hex is the field the swatch actually renders, so it needs the same guard.
    product = _product(category, hsn_code="61091000")
    product.save()
    variant = ProductVariant(product=product, size="M", color="Black", color_hex="};evil{")

    with pytest.raises(ValidationError):
        variant.full_clean()


def test_urls_match_the_map_the_chrome_links_against(category):
    # rebuild/03-architecture.md §4 is the contract; header and footer hardcode these paths.
    product = _product(category, hsn_code="61091000")
    collection = Collection(name="New arrivals", slug="new-arrivals")

    assert category.get_absolute_url() == "/shop/hoodies/"
    assert product.get_absolute_url() == "/product/signature-hoodie/"
    assert collection.get_absolute_url() == "/collections/new-arrivals/"
