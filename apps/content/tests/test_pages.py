"""Content models M9.4: page and FAQ bodies are sanitised on save (§12), and the lookups the
storefront calls return only what should be public."""

from __future__ import annotations

import pytest

from apps.content import services
from apps.content.models import FaqEntry, NewsletterSubscriber, Page

pytestmark = pytest.mark.django_db


def test_a_page_body_is_sanitised_on_save():
    page = Page.objects.create(
        slug="about",
        title="About",
        body='<p>Hello</p><script>alert(1)</script><a href="javascript:evil()">x</a>',
        is_published=True,
    )
    assert "<script>" not in page.body
    assert "alert(1)" not in page.body
    assert "javascript:" not in page.body
    assert "<p>Hello</p>" in page.body  # ordinary formatting survives


def test_a_faq_answer_is_sanitised_on_save():
    entry = FaqEntry.objects.create(question="Is it safe?", answer="<b>Yes</b><script>x()</script>")
    assert "<b>Yes</b>" in entry.answer
    assert "<script>" not in entry.answer


def test_only_published_pages_are_served():
    Page.objects.create(slug="terms", title="Terms", body="<p>t</p>", is_published=True)
    Page.objects.create(slug="draft", title="Draft", body="<p>d</p>", is_published=False)
    assert services.get_published_page("terms") is not None
    assert services.get_published_page("draft") is None
    assert services.get_published_page("missing") is None


def test_faq_entries_group_by_category_and_skip_inactive():
    FaqEntry.objects.create(question="Q1", answer="a", category="Shipping", display_order=1)
    FaqEntry.objects.create(question="Q2", answer="a", category="Shipping", display_order=0)
    FaqEntry.objects.create(question="Q3", answer="a", category="", is_active=False)
    grouped = services.faq_grouped()
    assert list(grouped.keys()) == ["Shipping"]
    assert [e.question for e in grouped["Shipping"]] == ["Q2", "Q1"]  # display order


def test_a_subscriber_is_only_subscribed_once_confirmed():
    sub = NewsletterSubscriber.objects.create(email="a@example.com")
    assert sub.is_subscribed is False
