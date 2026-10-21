"""Storefront review writing (M9.2).

One page, reachable from the account order detail and the review-request email. The order line is
loaded from a queryset scoped to the signed-in user, so an id from the URL can never reach another
customer's purchase, and the service re-checks the buy and the one-review-per-line rule.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from apps.orders.models import OrderItem

from . import services
from .forms import ReviewForm


@login_required
def write_review(request, item_id):
    item = get_object_or_404(
        OrderItem.objects.select_related("order", "variant__product"),
        id=item_id,
        order__user=request.user,
    )
    if not services.can_review(request.user, item):
        messages.error(request, "This item is not available to review.")
        return redirect("account-order-detail", order_number=item.order.order_number)

    form = ReviewForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            services.create_review(
                request.user,
                item,
                rating=form.cleaned_data["rating"],
                title=form.cleaned_data["title"],
                body=form.cleaned_data["body"],
                fit_feedback=form.cleaned_data["fit_feedback"],
            )
        except services.ReviewError as exc:
            messages.error(request, exc.message)
        else:
            messages.success(
                request, "Thanks. Your review is pending moderation and appears once approved."
            )
            return redirect("account-order-detail", order_number=item.order.order_number)

    return render(request, "account/review_form.html", {"form": form, "item": item})
