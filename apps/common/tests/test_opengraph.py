"""Open Graph, Twitter cards and robots.txt (M9.10).

The silent failure here is a shared link with no preview, so the test pins the tags onto a real
page rather than the template in isolation. robots.txt gets its own guard: it must point crawlers
at the sitemap and keep them out of private areas, without ever naming the secret admin paths."""

import pytest
from django.conf import settings
from django.test import Client

pytestmark = pytest.mark.django_db


@pytest.fixture
def client():
    return Client()


def test_the_home_page_carries_open_graph_and_a_twitter_card(client, catalogue):
    body = client.get("/").content.decode()
    assert '<meta property="og:type" content="website">' in body
    assert 'property="og:title"' in body
    assert 'property="og:url"' in body
    assert "og-default.png" in body  # brand default image when a page has none of its own
    assert '<meta name="twitter:card" content="summary_large_image">' in body


def test_a_product_page_sets_the_product_og_type(client, catalogue):
    body = client.get("/product/green-hoodie/").content.decode()
    assert '<meta property="og:type" content="product">' in body
    assert 'property="og:image"' in body


def test_robots_points_at_the_sitemap_and_blocks_private_areas(client):
    resp = client.get("/robots.txt")
    assert resp.status_code == 200
    assert resp["Content-Type"].startswith("text/plain")
    body = resp.content.decode()
    assert "Disallow: /account/" in body
    assert "Disallow: /api/" in body
    assert "Sitemap: http://testserver/sitemap.xml" in body


def test_robots_never_publishes_the_secret_admin_or_backoffice_paths(client):
    body = client.get("/robots.txt").content.decode()
    assert settings.ADMIN_URL.rstrip("/") not in body
    assert settings.BACKOFFICE_URL.rstrip("/") not in body
