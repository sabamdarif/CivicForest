"""sitemap.xml (L4): only pages a customer can actually reach.

The failure this guards against is quiet and expensive. A sitemap that lists a retired product,
an inactive category or a route a later milestone has not mounted feeds search engines 404s,
and nothing in a browser tells you it is happening.
"""

import re
from xml.etree import ElementTree

import pytest
from django.test import Client

from apps.catalog.models import Category, Collection, Product

pytestmark = pytest.mark.django_db

NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}


@pytest.fixture
def urls(catalogue):
    response = Client().get("/sitemap.xml")
    assert response.status_code == 200
    assert "xml" in response.headers["Content-Type"]
    tree = ElementTree.fromstring(response.content)
    return [node.text for node in tree.findall("s:url/s:loc", NS)]


def _paths(urls: list[str]) -> set[str]:
    return {re.sub(r"^https?://[^/]+", "", url) for url in urls}


def test_it_parses_and_covers_the_routes_that_exist(urls):
    assert {"/", "/shop/", "/collections/"} <= _paths(urls)


def test_every_live_product_category_and_collection_is_listed(urls):
    paths = _paths(urls)

    assert "/product/plain-tee/" in paths
    assert "/shop/hoodies/" in paths
    assert "/collections/new-arrivals/" in paths


def test_nothing_a_visitor_cannot_reach_is_listed(urls):
    paths = _paths(urls)

    assert "/product/retired-tee/" not in paths, "the inactive product"


def test_switching_something_off_takes_it_out(catalogue):
    Product.objects.filter(slug="plain-tee").update(is_active=False)
    Category.objects.filter(slug="hoodies").update(is_active=False)
    Collection.objects.filter(slug="staples").update(is_active=False)

    body = Client().get("/sitemap.xml").content.decode()

    assert "plain-tee" not in body
    assert "/shop/hoodies/" not in body
    assert "staples" not in body


def test_every_url_is_absolute_and_carries_a_last_modified(urls):
    assert urls and all(url.startswith("http") for url in urls)

    tree = ElementTree.fromstring(Client().get("/sitemap.xml").content)
    entries = tree.findall("s:url", NS)
    product = next(node for node in entries if "/product/" in node.find("s:loc", NS).text)
    assert product.find("s:lastmod", NS) is not None


def test_the_domain_is_not_djangos_placeholder(urls):
    assert not any("example.com" in url for url in urls)
