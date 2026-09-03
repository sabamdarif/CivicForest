"""JSON-LD (L4): valid, absolute, and never claiming more than the site can back.

The two failure modes worth a test are silent. A relative URL in JSON-LD is simply ignored by
every consumer, and an `aggregateRating` with no reviews behind it is a Google manual action
plus exactly the fabrication J9 forbids on the rest of the page. Neither shows up in a browser.
"""

import json
import re

import pytest
from django.test import Client

from apps.catalog.models import Product

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return Client()


def _nodes(client, url: str) -> list[dict]:
    response = client.get(url)
    assert response.status_code == 200, url
    blocks = re.findall(
        r'<script type="application/ld\+json">(.*?)</script>',
        response.content.decode(),
        re.S,
    )
    return [json.loads(block) for block in blocks]


def _by_type(nodes: list[dict]) -> dict[str, dict]:
    return {node["@type"]: node for node in nodes}


def test_the_home_page_declares_the_organisation_and_the_site(client, catalogue):
    nodes = _by_type(_nodes(client, "/"))

    assert set(nodes) == {"Organization", "WebSite"}
    assert nodes["WebSite"]["potentialAction"]["@type"] == "SearchAction"


def test_every_browse_page_carries_its_breadcrumb_trail(client, catalogue):
    for url in ("/shop/", "/shop/t-shirts/", "/collections/", "/collections/staples/"):
        nodes = _by_type(_nodes(client, url))
        assert "BreadcrumbList" in nodes, url


def test_a_breadcrumb_trail_is_positioned_and_absolute(client, catalogue):
    trail = _by_type(_nodes(client, "/shop/t-shirts/"))["BreadcrumbList"]["itemListElement"]

    assert [item["position"] for item in trail] == [1, 2, 3]
    assert [item["name"] for item in trail] == ["Home", "Shop", "T-Shirts"]
    assert all(item["item"].startswith("http://") for item in trail)


def test_a_product_declares_one_offer_at_the_price_the_page_shows(client, catalogue):
    nodes = _by_type(_nodes(client, "/product/green-hoodie/"))
    offer = nodes["Product"]["offers"]

    # The hoodie's cheapest sellable variant is the 1299 override, not the 1499 base.
    assert offer["price"] == "1299.00"
    assert offer["priceCurrency"] == "INR"
    assert offer["availability"].endswith("/InStock")


def test_a_discounted_product_states_the_printed_price_as_well(client, catalogue):
    offer = _by_type(_nodes(client, "/product/graphic-tee/"))["Product"]["offers"]

    assert offer["price"] == "999.00"
    assert offer["priceSpecification"]["price"] == "1199.00"
    assert offer["priceSpecification"]["valueAddedTaxIncluded"] is True


def test_a_sold_out_product_says_so_rather_than_going_quiet(client, catalogue):
    Product.objects.get(slug="plain-tee").variants.update(stock_quantity=0)

    offer = _by_type(_nodes(client, "/product/plain-tee/"))["Product"]["offers"]

    assert offer["availability"].endswith("/OutOfStock")


def test_a_product_never_claims_a_rating_it_does_not_have(client, catalogue):
    product = _by_type(_nodes(client, "/product/plain-tee/"))["Product"]

    assert "aggregateRating" not in product
    assert "review" not in product


def test_the_required_product_properties_are_all_there(client, catalogue):
    product = _by_type(_nodes(client, "/product/plain-tee/"))["Product"]

    assert product["name"] == "Plain Tee"
    assert product["url"].startswith("http://")
    assert product["brand"]["name"] == "CivicForest Clothing"
    assert product["countryOfOrigin"] == "India"
    assert product["sku"]


def test_a_product_name_cannot_close_the_script_element(client, catalogue):
    hostile = Product.objects.get(slug="plain-tee")
    hostile.name = "</script><script>alert(1)</script>"
    hostile.save()

    body = client.get("/product/plain-tee/").content.decode()

    assert "</script><script>alert(1)" not in body
    # Still parses, and the name survives intact inside the JSON.
    node = _by_type(_nodes(client, "/product/plain-tee/"))["Product"]
    assert node["name"] == hostile.name


def test_the_canonical_url_drops_the_filters(client, catalogue):
    body = client.get("/shop/?size=M&sort=newest&page=1").content.decode()

    assert re.search(r'<link rel="canonical" href="http://[^"?]+/shop/">', body)
