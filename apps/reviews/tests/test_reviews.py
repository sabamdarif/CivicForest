"""Reviews M9.1: a review only attaches to a proven purchase, and only a published one counts.

The adversarial line is "done when a review cannot be posted by someone who did not buy the
product": the not-a-purchaser and already-reviewed paths are asserted, alongside the aggregate
moving only on publish and hide.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from apps.common.factories import (
    OrderFactory,
    OrderItemFactory,
    ProductVariantFactory,
    UserFactory,
)
from apps.orders.models import Order
from apps.reviews import services
from apps.reviews.models import Review

pytestmark = pytest.mark.django_db


def _paid_line(user=None, variant=None):
    user = user or UserFactory()
    variant = variant or ProductVariantFactory()
    order = OrderFactory(user=user, status=Order.Status.PAID)
    return OrderItemFactory(order=order, variant=variant), user, variant.product


def test_a_buyer_can_review_a_paid_line():
    item, user, _ = _paid_line()
    review = services.create_review(
        user, item, rating=5, title="Great", body="Love it", fit_feedback="true_to_size"
    )
    assert review.status == Review.Status.PENDING


def test_a_non_purchaser_cannot_review():
    item, _, _ = _paid_line()
    stranger = UserFactory()
    with pytest.raises(services.ReviewError) as exc:
        services.create_review(stranger, item, rating=5, title="", body="", fit_feedback="")
    assert exc.value.code == "not_purchaser"


def test_an_unpaid_order_cannot_be_reviewed():
    user = UserFactory()
    order = OrderFactory(user=user, status=Order.Status.PAYMENT_PENDING)
    item = OrderItemFactory(order=order)
    assert services.can_review(user, item) is False


def test_a_line_can_be_reviewed_only_once():
    item, user, _ = _paid_line()
    services.create_review(user, item, rating=4, title="", body="", fit_feedback="")
    with pytest.raises(services.ReviewError) as exc:
        services.create_review(user, item, rating=1, title="", body="", fit_feedback="")
    assert exc.value.code == "already_reviewed"


def test_only_published_reviews_move_the_cached_aggregate():
    product = ProductVariantFactory().product
    reviews = {}
    for rating in (4, 2):
        item, user, _ = _paid_line(variant=product.variants.first())
        reviews[rating] = services.create_review(
            user, item, rating=rating, title="", body="", fit_feedback=""
        )

    product.refresh_from_db()
    assert product.rating_count == 0  # pending reviews do not count

    services.publish_review(reviews[4])
    services.publish_review(reviews[2])
    product.refresh_from_db()
    assert product.rating_count == 2
    assert product.rating_average == Decimal("3.00")

    services.reject_review(reviews[4])
    product.refresh_from_db()
    assert product.rating_count == 1
    assert product.rating_average == Decimal("2.00")


def test_the_summary_reports_distribution_and_fit():
    product = ProductVariantFactory().product
    for rating, fit in ((5, "true_to_size"), (5, "true_to_size"), (3, "runs_small")):
        item, user, _ = _paid_line(variant=product.variants.first())
        review = services.create_review(
            user, item, rating=rating, title="", body="", fit_feedback=fit
        )
        services.publish_review(review)

    summary = services.product_review_summary(product)
    assert summary["count"] == 3
    assert summary["distribution"][5] == 2
    assert summary["fit"]["dominant"] == "true_to_size"
    assert summary["fit"]["dominant_pct"] == 67
