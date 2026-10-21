"""Newsletter double opt-in (M9.8, J5): subscribing only mails a confirm link and never opts
anyone in on its own, the welcome code is minted once on the first confirmation, unsubscribe is a
one-click GET with no login, and a tampered token changes nothing."""

from __future__ import annotations

import pytest
from django.core import mail
from django.test import Client

from apps.cart.models import Coupon
from apps.content import services
from apps.content.models import NewsletterSubscriber

pytestmark = pytest.mark.django_db


def test_subscribing_does_not_opt_in_or_issue_a_code():
    # Consent is the confirm click, never pre-selected: a subscribe leaves the row unconfirmed
    # and mints no coupon, so applying and walking away spends nothing.
    resp = Client().post("/newsletter/subscribe/", {"email": "Ravi@Example.com"})
    assert resp.status_code == 302
    sub = NewsletterSubscriber.objects.get(email="ravi@example.com")  # normalised
    assert not sub.is_subscribed
    assert Coupon.objects.count() == 0
    assert len(mail.outbox) == 1  # confirm link only


def test_confirming_mints_the_welcome_code_exactly_once():
    services.subscribe("ravi@example.com")
    token = services.confirm_token("ravi@example.com")
    services.confirm_subscription(token)
    services.confirm_subscription(token)  # replayed link
    sub = NewsletterSubscriber.objects.get(email="ravi@example.com")
    assert sub.is_subscribed
    assert Coupon.objects.count() == 1
    coupon = Coupon.objects.get()
    assert coupon.discount_type == Coupon.DiscountType.PERCENT
    assert coupon.first_order_only and coupon.max_uses == 1
    assert coupon.code in mail.outbox[-1].body  # welcome email carries the code


def test_unsubscribe_is_one_click_and_needs_no_login():
    services.subscribe("ravi@example.com")
    services.confirm_subscription(services.confirm_token("ravi@example.com"))
    token = services.unsubscribe_token("ravi@example.com")
    resp = Client().get(f"/newsletter/unsubscribe/{token}/")  # anonymous GET
    assert resp.status_code == 200
    sub = NewsletterSubscriber.objects.get(email="ravi@example.com")
    assert sub.unsubscribed_at is not None
    assert not sub.is_subscribed


def test_a_tampered_confirm_token_changes_nothing():
    services.subscribe("ravi@example.com")
    resp = Client().get("/newsletter/confirm/not-a-real-token/")
    assert resp.status_code == 400
    assert NewsletterSubscriber.objects.get(email="ravi@example.com").confirmed_at is None
    assert Coupon.objects.count() == 0


def test_a_confirm_token_cannot_be_replayed_as_an_unsubscribe():
    # Separate salts: a confirm link handed to the unsubscribe route is rejected, and vice versa.
    services.subscribe("ravi@example.com")
    confirm = services.confirm_token("ravi@example.com")
    assert services.unsubscribe(confirm) is None
