"""The catalogue's guards: a swatch hex that cannot carry CSS, and the country of origin a
product cannot be saved without.

The hex guard exists because an unvalidated swatch hex is a style attribute written straight
into every page that lists the product.
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


def test_country_of_origin_is_never_blank(category):
    # The field has a default and the form requires it, so a blank is rejected.
    with pytest.raises(ValidationError) as exc:
        _product(category, country_of_origin="").full_clean()

    assert "country_of_origin" in exc.value.message_dict


def test_a_complete_product_passes(category):
    _product(category, is_active=True).full_clean()


@pytest.mark.parametrize("bad", ["red", "#12", "#1f3d2b; background:url(//evil)", "1f3d2b"])
def test_a_swatch_hex_cannot_carry_anything_but_a_hex(bad):
    with pytest.raises(ValidationError):
        Color(name="Suspicious", hex=bad).full_clean()


@pytest.mark.parametrize("good", ["#fff", "#1f3d2b", ""])
def test_a_real_hex_or_none_at_all_is_accepted(good):
    Color(name="Forest", hex=good).full_clean()


def test_the_variant_swatch_is_validated_too(category):
    # color_hex is the field the swatch actually renders, so it needs the same guard.
    product = _product(category)
    product.save()
    variant = ProductVariant(product=product, size="M", color="Black", color_hex="};evil{")

    with pytest.raises(ValidationError):
        variant.full_clean()


def test_urls_match_the_map_the_chrome_links_against(category):
    # rebuild/03-architecture.md §4 is the contract; header and footer hardcode these paths.
    product = _product(category)
    collection = Collection(name="New arrivals", slug="new-arrivals")

    assert category.get_absolute_url() == "/shop/hoodies/"
    assert product.get_absolute_url() == "/product/signature-hoodie/"
    assert collection.get_absolute_url() == "/collections/new-arrivals/"
