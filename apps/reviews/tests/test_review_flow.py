"""Reviews M9.2: the write form is scoped to the buyer, only published reviews reach the product
page (and its JSON-LD), moderation is permission-gated, and the request email is sent once."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.contrib.auth.models import Permission
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.common.factories import (
    OrderFactory,
    OrderItemFactory,
    ProductVariantFactory,
    StaffUserFactory,
    UserFactory,
    login_staff_with_mfa,
)
from apps.common.models import OutboundEmail
from apps.orders.models import Order, Shipment
from apps.reviews import services
from apps.reviews.models import Review

pytestmark = pytest.mark.django_db


def _staff_with(client, *codenames):
    user = StaffUserFactory()
    for codename in codenames:
        user.user_permissions.add(Permission.objects.get(codename=codename))
    login_staff_with_mfa(client, user=user)
    return user


def _paid_line(user, variant=None):
    order = OrderFactory(user=user, status=Order.Status.PAID)
    return OrderItemFactory(order=order, variant=variant or ProductVariantFactory())


# ── Storefront write form ─────────────────────────────────────────────────────
def test_the_buyer_can_open_and_submit_the_form():
    user = UserFactory()
    item = _paid_line(user)
    client = Client()
    client.force_login(user)
    url = reverse("review-write", kwargs={"item_id": item.id})

    assert client.get(url).status_code == 200
    resp = client.post(
        url, {"rating": "5", "fit_feedback": "true_to_size", "title": "Nice", "body": "Soft"}
    )
    assert resp.status_code == 302
    review = Review.objects.get(order_item=item)
    assert review.status == Review.Status.PENDING and review.rating == 5


def test_another_customer_cannot_reach_someone_elses_line():
    item = _paid_line(UserFactory())
    client = Client()
    client.force_login(UserFactory())
    resp = client.post(
        reverse("review-write", kwargs={"item_id": item.id}), {"rating": "1", "body": "x"}
    )
    assert resp.status_code == 404
    assert not Review.objects.filter(order_item=item).exists()


# ── Product page: only published rows, and the aggregateRating that follows ─────
def _publish_review(variant, rating=5):
    item = _paid_line(UserFactory(), variant=variant)
    review = services.create_review(
        item.order.user,
        item,
        rating=rating,
        title="Great tee",
        body="Lovely fabric",
        fit_feedback="",
    )
    services.publish_review(review)
    return review


def test_the_product_page_shows_only_published_reviews_and_aggregate():
    variant = ProductVariantFactory()
    product = variant.product
    client = Client()

    body = client.get(product.get_absolute_url()).content.decode()
    assert "No reviews yet" in body
    assert "aggregateRating" not in body

    _publish_review(variant)
    # A second, still-pending review must not leak onto the page.
    pending_item = _paid_line(UserFactory(), variant=variant)
    services.create_review(
        pending_item.order.user,
        pending_item,
        rating=1,
        title="hidden",
        body="pending words",
        fit_feedback="",
    )

    body = client.get(product.get_absolute_url()).content.decode()
    assert "Lovely fabric" in body
    assert "pending words" not in body
    assert "aggregateRating" in body


# ── Back-office moderation ──────────────────────────────────────────────────────
def test_a_view_only_role_cannot_publish_or_reject():
    variant = ProductVariantFactory()
    item = _paid_line(UserFactory(), variant=variant)
    review = services.create_review(
        item.order.user, item, rating=4, title="", body="ok", fit_feedback=""
    )
    client = Client()
    _staff_with(client, "view_review")
    resp = client.post(
        reverse("backoffice:review_action", kwargs={"pk": review.id}), {"action": "publish"}
    )
    assert resp.status_code == 404
    review.refresh_from_db()
    assert review.status == Review.Status.PENDING


def test_a_moderator_can_publish_and_the_aggregate_moves():
    variant = ProductVariantFactory()
    item = _paid_line(UserFactory(), variant=variant)
    review = services.create_review(
        item.order.user, item, rating=4, title="", body="ok", fit_feedback=""
    )
    client = Client()
    _staff_with(client, "view_review", "change_review")
    resp = client.post(
        reverse("backoffice:review_action", kwargs={"pk": review.id}), {"action": "publish"}
    )
    assert resp.status_code == 302
    review.refresh_from_db()
    assert review.status == Review.Status.PUBLISHED
    variant.product.refresh_from_db()
    assert variant.product.rating_count == 1


# ── Review-request sweep (I10) ──────────────────────────────────────────────────
def _delivered_order(user, days_ago):
    order = OrderFactory(user=user, status=Order.Status.DELIVERED)
    OrderItemFactory(order=order)
    Shipment.objects.create(
        order=order,
        kind=Shipment.Kind.STOCK,
        delivered_at=timezone.now() - timedelta(days=days_ago),
    )
    return order


def test_the_review_request_is_sent_once_after_the_delay():
    from apps.orders import services as order_services

    old = _delivered_order(UserFactory(), days_ago=4)
    fresh = _delivered_order(UserFactory(), days_ago=1)

    assert order_services.send_pending_review_requests(50) == 1
    old.refresh_from_db()
    fresh.refresh_from_db()
    assert old.review_requested_at is not None
    assert fresh.review_requested_at is None
    assert OutboundEmail.objects.filter(template="order:review_request").count() == 1

    # A second sweep sends nothing more.
    assert order_services.send_pending_review_requests(50) == 0
