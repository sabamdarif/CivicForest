"""Review business logic: who may write one, moderation, and the cached product aggregate.

Views and the back-office call these; they never write ``Review.status`` or the product's rating
columns directly. Eligibility starts from the customer's own paid order lines, so a review can
only attach to a purchase (build-plan M9 "done when"). The aggregate the product page reads is
recomputed here on every publish or hide, counting published rows only, so an unmoderated review
never moves it.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

from django.db.models import Avg, Count
from django.utils import timezone

from apps.orders.models import Order, OrderItem

from .models import Review


class ReviewError(Exception):
    def __init__(self, message: str, code: str = "review_error"):
        super().__init__(message)
        self.message = message
        self.code = code


def _paid_items(user):
    """The user's order lines whose order has been paid: the only lines a review may attach to."""
    return OrderItem.objects.filter(
        order__user=user, order__status__in=Order.PAID_STATUSES
    ).select_related("order")


def eligible_items(user):
    """Paid lines this user has not reviewed yet, newest first (drives the write-a-review links)."""
    return _paid_items(user).filter(review__isnull=True).order_by("-order__created_at")


def can_review(user, order_item: OrderItem) -> bool:
    if order_item.order.user_id != user.id or not order_item.order.is_paid:
        return False
    return not Review.objects.filter(order_item=order_item).exists()


def create_review(
    user, order_item: OrderItem, *, rating: int, title: str, body: str, fit_feedback: str
) -> Review:
    """Record a pending review against a bought line. Raises if the line is not the user's, not
    paid, or already reviewed. Published only after moderation (K4)."""
    if order_item.order.user_id != user.id or not order_item.order.is_paid:
        raise ReviewError("You can only review something you have bought.", code="not_purchaser")
    if Review.objects.filter(order_item=order_item).exists():
        raise ReviewError("You have already reviewed this item.", code="already_reviewed")
    return Review.objects.create(
        product_id=order_item.variant.product_id if order_item.variant_id else None,
        user=user,
        order_item=order_item,
        rating=rating,
        title=title.strip()[:120],
        body=body.strip(),
        fit_feedback=fit_feedback if fit_feedback in Review.FitFeedback.values else "",
        status=Review.Status.PENDING,
    )


def publish_review(review: Review) -> Review:
    review.status = Review.Status.PUBLISHED
    review.published_at = review.published_at or timezone.now()
    review.save(update_fields=["status", "published_at", "updated_at"])
    recompute_product_rating(review.product_id)
    return review


def reject_review(review: Review) -> Review:
    was_published = review.status == Review.Status.PUBLISHED
    review.status = Review.Status.REJECTED
    review.save(update_fields=["status", "updated_at"])
    if was_published:
        recompute_product_rating(review.product_id)
    return review


def recompute_product_rating(product_id) -> None:
    """Refresh the product's cached average and count from its published reviews only."""
    from apps.catalog.models import Product

    if not product_id:
        return
    agg = Review.objects.filter(product_id=product_id, status=Review.Status.PUBLISHED).aggregate(
        avg=Avg("rating"), count=Count("id")
    )
    average = Decimal(agg["avg"] or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    Product.objects.filter(pk=product_id).update(
        rating_average=average, rating_count=agg["count"] or 0
    )


def product_review_summary(product) -> dict:
    """Everything the product page renders: the published reviews, the 1-5 star distribution, the
    fit-feedback split ("72% say true to size"), and the cached average and count."""
    reviews = list(
        Review.objects.filter(product=product, status=Review.Status.PUBLISHED)
        .select_related("user")
        .order_by("-published_at")
    )
    distribution = dict.fromkeys(range(5, 0, -1), 0)
    fit_counts = dict.fromkeys(Review.FitFeedback.values, 0)
    for review in reviews:
        distribution[review.rating] = distribution.get(review.rating, 0) + 1
        if review.fit_feedback:
            fit_counts[review.fit_feedback] += 1

    fit_total = sum(fit_counts.values())
    fit = None
    if fit_total:
        percentages = {value: round(count * 100 / fit_total) for value, count in fit_counts.items()}
        dominant = max(fit_counts, key=fit_counts.get)
        fit = {
            "percentages": percentages,
            "dominant": dominant,
            "dominant_label": Review.FitFeedback(dominant).label,
            "dominant_pct": percentages[dominant],
        }
    # Count and average come from this fresh published set, not the product's cached columns, so
    # the page is self-consistent even if the cache has not been recomputed yet. The cache exists
    # for the grid and JSON-LD, which do not load the review list.
    count = len(reviews)
    average = (
        (Decimal(sum(r.rating for r in reviews)) / count).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        if count
        else Decimal("0.00")
    )
    return {
        "reviews": reviews,
        "count": count,
        "average": average,
        "distribution": distribution,
        "fit": fit,
    }
