"""The home page is data, so the tests are about what the data can and cannot do to it.

The one that matters: switching a band off has to take its heading with it, and a band whose
catalogue content is empty must not render a heading over nothing. A page that shows "Just
landed" above an empty strip is worse than a page with one section fewer.
"""

import re

import pytest
from django.core.exceptions import ValidationError
from django.test import Client

from apps.catalog.models import Category, Product
from apps.content.models import HomeSection

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def product():
    category = Category.objects.create(name="Hoodies", slug="hoodies")
    return Product.objects.create(
        name="Signature Hoodie",
        slug="signature-hoodie",
        category=category,
        base_price="1199.00",
        hsn_code="61102000",
    )


def _body(client) -> str:
    response = client.get("/")
    assert response.status_code == 200
    return response.content.decode()


def test_the_migration_seeds_every_band_the_template_can_render():
    assert set(HomeSection.objects.values_list("kind", flat=True)) == set(HomeSection.Kind.values)


def test_the_bands_render_in_the_order_staff_put_them_in(client, product):
    body = _body(client)
    order = re.findall(r"hero-band|trust-strip|tiles|values", body)

    assert order.index("hero-band") < order.index("trust-strip") < order.index("tiles")
    assert order.index("tiles") < order.index("values")


def test_reordering_a_band_reorders_the_page(client, product):
    HomeSection.objects.filter(kind="values").update(display_order=0)

    body = _body(client)

    assert body.index("values__list") < body.index("hero-band")


def test_switching_a_band_off_takes_its_heading_with_it(client, product):
    assert "Just landed" in _body(client)

    HomeSection.objects.filter(kind="new_arrivals").update(is_active=False)

    body = _body(client)
    assert "Just landed" not in body
    assert "product-grid" not in body


def test_a_band_with_nothing_in_it_renders_no_heading(client):
    # No products and no categories at all: the copy is still configured, so only the guard
    # in the template stops "Find your style" appearing above an empty grid.
    body = _body(client)

    assert "Find your style" not in body
    assert "Just landed" not in body
    assert "hero-band" in body, "the hero needs no catalogue"


def test_the_hero_falls_back_to_the_brand_still_when_nobody_has_uploaded_one(client):
    body = _body(client)

    assert "img/seed/hero-black-tee.png" in body


def test_a_section_link_cannot_carry_a_javascript_url():
    section = HomeSection.objects.get(kind="hero")
    section.target = "javascript:alert(1)"

    with pytest.raises(ValidationError) as exc:
        section.full_clean()

    assert "target" in exc.value.message_dict


def test_the_page_costs_a_bounded_number_of_queries(client, product, django_assert_num_queries):
    # Prefetching is what keeps a grid of products off the N+1 path; if this number climbs,
    # something started querying inside the loop. Two of the eight are chrome: the
    # announcement bar and the categories in the SHOP menu.
    with django_assert_num_queries(8):
        client.get("/")
