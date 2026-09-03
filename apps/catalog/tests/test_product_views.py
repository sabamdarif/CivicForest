"""The product page: what L9 requires before add-to-cart, and a picker that works without JS.

Two things here are load-bearing. Everything the Consumer Protection (E-commerce) Rules require
has to be on the page before the button, not one accordion click away. And a size is only
struck through when it is out of stock *in the colour on screen*, because striking a size that
another colour has in stock loses a sale for no reason.
"""

import re

import pytest
from django.test import Client

from apps.catalog.models import Product, ProductVariant, SizeChart

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return Client()


def _get(client, url: str) -> str:
    response = client.get(url)
    assert response.status_code == 200, url
    return response.content.decode()


def _sizes(body: str) -> dict[str, bool]:
    """{size label: is offered} read off the rendered picker."""
    offered = {}
    for block in re.findall(r'<label class="size-option[^"]*">.*?</label>', body, re.S):
        label = re.search(r"<span>([^<]+)</span>", block).group(1)
        offered[label] = "size-option--out" not in block
    return offered


# ── Reachability ─────────────────────────────────────────────────────────────
def test_a_live_product_renders_and_a_retired_one_is_a_404(client, catalogue):
    assert '<h1 class="buy__name">Plain Tee</h1>' in _get(client, "/product/plain-tee/")
    assert client.get("/product/retired-tee/").status_code == 404
    assert client.get("/product/ghost/").status_code == 404


def test_the_breadcrumb_walks_back_through_the_category(client, catalogue):
    body = _get(client, "/product/green-hoodie/")

    assert 'href="/shop/"' in body
    assert 'href="/shop/hoodies/"' in body


# ── L9: everything visible before the button ─────────────────────────────────
def test_the_page_carries_everything_the_law_requires_without_opening_anything(client, catalogue):
    """L9: none of this may be hidden behind an interaction, so it has to sit in the buy panel
    rather than inside one of the accordions below it."""
    body = _get(client, "/product/plain-tee/")
    panel = body[: body.index('<div class="accordions">')]

    assert "Inclusive of all taxes" in panel, "C3: prices are shown tax-inclusive"
    assert "Country of origin" in panel and "India" in panel
    assert "business days" in panel, "the delivery estimate"
    assert "7 days from delivery" in panel, "the return window"


def test_no_rating_is_invented_before_reviews_exist(client, catalogue):
    body = _get(client, "/product/plain-tee/")

    assert "AggregateRating" not in body
    assert 'class="rating"' not in body


# ── The picker (E2, E4) ──────────────────────────────────────────────────────
def test_a_size_out_of_stock_in_this_colour_is_struck_through_not_hidden(client, catalogue):
    body = _get(client, "/product/plain-tee/")

    # Black has M in stock and L at zero, so L is offered and visibly gone.
    assert _sizes(body) == {"M": True, "L": False}
    assert 'value="L"' in body and "disabled" in body


def test_swapping_colour_re_renders_the_sizes_that_colour_actually_has(client, catalogue):
    beige = _get(client, "/product/plain-tee/?color=Beige")

    assert _sizes(beige) == {"M": True}, "Beige is only made in M"
    assert 'name="color" value="Beige"' in beige


def test_a_colour_nobody_sells_falls_back_instead_of_failing(client, catalogue):
    body = _get(client, "/product/plain-tee/?color=Chartreuse")

    assert 'name="color" value="Black"' in body


def test_the_first_size_offered_is_one_you_can_actually_buy(client, catalogue):
    # The hoodie's M is empty and its L is not, so L is what arrives selected.
    body = _get(client, "/product/green-hoodie/")

    assert re.search(r'value="L"[^>]*checked', body)


def test_the_price_follows_the_size_that_is_selected(client, catalogue):
    # The hoodie's L carries a 1299 override against a 1499 base.
    body = _get(client, "/product/green-hoodie/")

    assert "₹1,299.00" in body


def test_a_product_with_nothing_left_cannot_be_added(client, catalogue):
    ProductVariant.objects.filter(product__slug="plain-tee").update(stock_quantity=0)

    body = _get(client, "/product/plain-tee/")

    assert "Sold out" in body
    assert "Add to cart" not in body


def test_a_stock_line_appears_only_when_the_stock_is_really_that_low(client, catalogue, settings):
    settings.LOW_STOCK_THRESHOLD = 3

    assert "Only" not in _get(client, "/product/plain-tee/"), "five left is not low"

    ProductVariant.objects.filter(product__slug="plain-tee", size="M", color="Black").update(
        stock_quantity=2
    )

    assert "Only 2 left" in _get(client, "/product/plain-tee/")


# ── The form the page posts ──────────────────────────────────────────────────
def test_add_to_cart_is_a_plain_form_that_sends_no_price(client, catalogue):
    body = _get(client, "/product/plain-tee/")
    form = re.search(r'<form class="buy__form".*?</form>', body, re.S).group(0)

    assert 'method="post" action="/cart/add/"' in form
    assert 'name="csrfmiddlewaretoken"' in form
    assert 'name="product" value="plain-tee"' in form
    assert 'name="size"' in form and 'name="color"' in form
    assert "price" not in form and "amount" not in form


def test_the_confirmation_after_adding_shows_up_on_the_page(client, catalogue):
    client.post(
        "/cart/add/",
        {"product": "plain-tee", "size": "M", "color": "Black", "quantity": "1"},
    )

    assert "is in your cart." in _get(client, "/product/plain-tee/")


# ── The rest of the page ─────────────────────────────────────────────────────
def test_the_size_chart_shows_up_for_a_category_that_has_one(client, catalogue):
    assert "size-chart" not in _get(client, "/product/plain-tee/")

    SizeChart.objects.create(
        category=Product.objects.get(slug="plain-tee").category,
        rows=[["Size", "Chest"], ["M", "40"]],
        unit="in",
    )

    body = _get(client, "/product/plain-tee/")
    assert 'id="size-guide"' in body
    assert '<th scope="col">Chest</th>' in body


def test_the_related_row_leaves_out_the_product_itself(client, catalogue):
    body = _get(client, "/product/plain-tee/")

    assert "You may also like" not in body, "nothing else is live in T-Shirts yet"

    Product.objects.create(
        name="Second Tee",
        slug="second-tee",
        category=Product.objects.get(slug="plain-tee").category,
        base_price="899",
        hsn_code="61091000",
    )

    body = _get(client, "/product/plain-tee/")
    assert "You may also like" in body
    assert "Second Tee" in body


def test_the_page_costs_a_bounded_number_of_queries(client, catalogue, django_assert_num_queries):
    # Two of the eight are chrome (the announcement bar and the SHOP menu). If this climbs,
    # something started querying inside a loop over the variants or the gallery.
    with django_assert_num_queries(8):
        client.get("/product/plain-tee/")


def test_the_recently_viewed_strip_is_rendered_from_the_cookie_the_browser_wrote(client, catalogue):
    assert "Recently viewed" not in _get(client, "/product/plain-tee/")

    client.cookies["cf_recent"] = "green-hoodie,graphic-tee"
    body = _get(client, "/product/plain-tee/")

    assert "Recently viewed" in body
    assert body.index("Green Hoodie") < body.index("Graphic Tee"), "the cookie's order"


def test_a_hostile_cookie_cannot_reach_a_query(client, catalogue):
    client.cookies["cf_recent"] = "' OR 1=1 --,../../etc/passwd,plain-tee"

    body = _get(client, "/product/green-hoodie/")

    assert "Recently viewed" in body, "the one real slug still shows"
    assert "etc/passwd" not in body
