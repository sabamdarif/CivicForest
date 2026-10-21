"""Static pages and FAQ (M9.5): the seed publishes them, the view serves only published slugs, and
the Returns and Exchanges page states both policies with the custom terms intact."""

from __future__ import annotations

import pytest
from django.core.management import call_command
from django.test import Client

from apps.content.models import Page

pytestmark = pytest.mark.django_db


@pytest.fixture
def seeded():
    call_command("seed_content")


def _body(client, url):
    resp = client.get(url)
    assert resp.status_code == 200, url
    return resp.content.decode()


def test_seed_publishes_the_static_pages(seeded):
    client = Client()
    body = _body(client, "/about/")
    assert "Our story" in body


def test_the_returns_page_states_both_policies(seeded):
    body = _body(Client(), "/returns-exchanges/")
    assert "Stock items" in body
    assert "Custom printed items" in body
    assert "unboxing video" in body  # Qikink's real term, not a softer promise
    assert "no size swap" in body or "no change-of-mind" in body


def test_an_unpublished_page_is_a_404(seeded):
    Page.objects.filter(slug="about").update(is_published=False)
    assert Client().get("/about/").status_code == 404


def test_the_faq_page_renders_entries_and_markup(seeded):
    body = _body(Client(), "/faq/")
    assert "Frequently asked questions" in body
    assert "FAQPage" in body  # JSON-LD
    assert "custom printed item" in body.lower()


def test_the_sitemap_lists_published_pages_only(seeded):
    body = _body(Client(), "/sitemap.xml")
    assert "/about/" in body
    Page.objects.filter(slug="about").update(is_published=False)
    assert "/about/" not in _body(Client(), "/sitemap.xml")


def test_the_grievance_page_shows_the_named_officer(settings):
    settings.GRIEVANCE_OFFICER_NAME = "Asha Rao"
    settings.GRIEVANCE_EMAIL = "grievance@civicforest.com"
    settings.GRIEVANCE_RESPONSE_HOURS = 48
    body = _body(Client(), "/grievance-redressal/")
    assert "Asha Rao" in body
    assert "grievance@civicforest.com" in body
    assert "48 hours" in body
