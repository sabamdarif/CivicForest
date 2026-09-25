"""Read-side aggregation for the back-office (dashboards, reports, queues).

Views stay thin by calling these. Nothing here writes; mutations live in the owning app's
services (orders, cart, catalog). `dashboard_context` is the O1 tile set plus the two chart
series; it grew out of the admin-index templatetag in `apps.common.templatetags.admin_dashboard`,
which stays for anyone still on Django admin.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.paginator import Page, Paginator
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.dateparse import parse_date

from apps.cart import services as cart_services
from apps.cart.models import Cart, CouponRedemption
from apps.catalog.models import Product, ProductVariant
from apps.common.formatting import rupees
from apps.custom_orders.models import CustomDesignOrder, DesignUpload
from apps.orders.models import Order, OrderItem
from apps.payments.models import Payment
from apps.search.models import SearchQueryLog

# Money captured and not reversed. Refunded and cancelled are excluded on purpose.
REVENUE_STATUSES = [
    Order.Status.PAID,
    Order.Status.PROCESSING,
    Order.Status.PARTIALLY_SHIPPED,
    Order.Status.SHIPPED,
    Order.Status.DELIVERED,
]


def _maybe(name: str, **query) -> str | None:
    """A back-office URL if it exists yet, else None.

    Tiles link to lists built in later M8 tasks; a tile renders without its link until then, so
    the dashboard never has to wait for the whole milestone."""
    try:
        url = reverse(f"backoffice:{name}")
    except NoReverseMatch:
        return None
    if query:
        from urllib.parse import urlencode

        url = f"{url}?{urlencode(query)}"
    return url


def dashboard_context() -> dict:
    today = timezone.localdate()
    start_30 = today - timedelta(days=29)
    start_7 = today - timedelta(days=6)

    window = Order.objects.filter(status__in=REVENUE_STATUSES, created_at__date__gte=start_30)
    by_day = {
        row["day"]: row
        for row in window.annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(revenue=Sum("total"), count=Count("id"))
        .order_by()
    }
    series = []
    for i in range(30):
        day = start_30 + timedelta(days=i)
        row = by_day.get(day, {})
        series.append(
            {
                "label": f"{day.day} {day.strftime('%b')}",
                "revenue": float(row.get("revenue") or 0),
                "orders": row.get("count") or 0,
            }
        )

    revenue_30d = window.aggregate(t=Sum("total"))["t"] or Decimal("0")
    revenue_7d = window.filter(created_at__date__gte=start_7).aggregate(t=Sum("total"))[
        "t"
    ] or Decimal("0")
    revenue_today = by_day.get(today, {}).get("revenue") or Decimal("0")
    orders_30d = window.count()
    units_30d = (
        OrderItem.objects.filter(
            order__status__in=REVENUE_STATUSES, order__created_at__date__gte=start_30
        ).aggregate(u=Sum("quantity"))["u"]
        or 0
    )
    new_customers = get_user_model().objects.filter(date_joined__date__gte=start_30).count()
    carts_30d = Cart.objects.filter(created_at__date__gte=start_30).count()
    abandoned = cart_services.carts_awaiting_reminder().count()

    status_counts = {
        row["status"]: row["count"]
        for row in Order.objects.values("status").annotate(count=Count("id")).order_by()
    }
    awaiting = status_counts.get(Order.Status.PAID, 0) + status_counts.get(
        Order.Status.PROCESSING, 0
    )
    pending_reviews = DesignUpload.objects.filter(
        review_status=DesignUpload.ReviewStatus.FLAGGED
    ).count()
    failed_qikink = CustomDesignOrder.objects.filter(
        submit_status=CustomDesignOrder.SubmitStatus.FAILED
    ).count()
    failed_payments = Payment.objects.filter(
        status=Payment.Status.FAILED, created_at__date__gte=start_30
    ).count()
    coupon_uses = CouponRedemption.objects.filter(created_at__date__gte=start_30).count()
    zero_results = SearchQueryLog.objects.filter(
        result_count=0, created_at__date__gte=start_30
    ).count()
    conversion = (orders_30d / carts_30d * 100) if carts_30d else 0

    tiles = [
        _tile("Revenue today", rupees(revenue_today, decimals=0)),
        _tile("Revenue, 7 days", rupees(revenue_7d, decimals=0)),
        _tile("Revenue, 30 days", rupees(revenue_30d, decimals=0)),
        _tile("Orders, 30 days", f"{orders_30d:,}", _maybe("orders")),
        _tile(
            "Avg order value",
            rupees(revenue_30d / orders_30d, decimals=0) if orders_30d else "no orders",
        ),
        _tile("Units sold, 30 days", f"{units_30d:,}"),
        _tile("New customers, 30 days", f"{new_customers:,}", _maybe("customers")),
        _tile("Awaiting fulfilment", f"{awaiting:,}", _maybe("orders", view="awaiting")),
        _tile("Designs to review", f"{pending_reviews:,}", _maybe("designs")),
        _tile("Failed Qikink jobs", f"{failed_qikink:,}", _maybe("designs", submit="failed")),
        _tile(
            "Failed payments, 30 days", f"{failed_payments:,}", _maybe("orders", payment="failed")
        ),
        _tile("Abandoned carts", f"{abandoned:,}"),
        _tile("Coupon uses, 30 days", f"{coupon_uses:,}", _maybe("coupons")),
        _tile("Zero-result searches, 30 days", f"{zero_results:,}"),
        _tile("Conversion rate, 30 days", f"{conversion:.1f}%"),
    ]

    return {
        "tiles": tiles,
        "series": series,
        "pipeline": [
            {"value": value, "label": label, "count": status_counts.get(value, 0)}
            for value, label in Order.Status.choices
        ],
        "top_products": list(
            OrderItem.objects.filter(
                order__status__in=REVENUE_STATUSES, order__created_at__date__gte=start_30
            )
            .values("product_name")
            .annotate(units=Sum("quantity"))
            .order_by("-units")[:8]
        ),
        "low_stock": ProductVariant.objects.filter(
            is_active=True, stock_quantity__lte=settings.LOW_STOCK_THRESHOLD
        )
        .select_related("product")
        .order_by("stock_quantity")[:8],
        "recent_orders": Order.objects.select_related("user")[:10],
    }


def _tile(label: str, value: str, url: str | None = None) -> dict:
    return {"label": label, "value": value, "url": url}


# ── Order queue (M8.4) ─────────────────────────────────────────────────────────
# Saved views are named query-string presets, not stored rows (O3): a link that seeds the whole
# filter set. The dashboard's "Awaiting fulfilment" and "Failed payments" tiles link to these.
ORDER_SAVED_VIEWS: dict[str, dict] = {
    "awaiting": {
        "label": "Awaiting dispatch",
        "filters": {"status": [Order.Status.PAID, Order.Status.PROCESSING]},
    },
    "custom_review": {
        "label": "Custom pending review",
        "filters": {
            "fulfilment": [Order.Fulfilment.CUSTOM, Order.Fulfilment.MIXED],
            "status": [Order.Status.PAID, Order.Status.PROCESSING],
        },
    },
    "payment_failed": {"label": "Payment failed", "filters": {"payment": "failed"}},
}

# The statuses a bulk action may set. Refund is excluded on purpose: it moves money and belongs
# on the guarded per-order action (M8.5), not a multi-select.
BULK_STATUS_CHOICES = [
    (Order.Status.PROCESSING, "Processing"),
    (Order.Status.SHIPPED, "Shipped"),
    (Order.Status.DELIVERED, "Delivered"),
    (Order.Status.CANCELLED, "Cancelled"),
]

ORDER_CSV_HEADER = [
    "order_number",
    "created_at",
    "status",
    "fulfilment",
    "email",
    "subtotal",
    "discount",
    "shipping_fee",
    "total",
    "coupon_code",
]

ORDER_QUEUE_PAGE_SIZE = 50


def parse_order_filters(params) -> dict:
    """Normalise the queue's GET params. A ``view`` naming a saved preset supplies the whole
    filter set; otherwise the explicit params are read. Every value is checked against the model
    choices, so a hand-edited query string cannot inject an unknown lookup."""
    view = params.get("view")
    if view in ORDER_SAVED_VIEWS:
        return {"view": view, **ORDER_SAVED_VIEWS[view]["filters"]}

    filters: dict = {}
    statuses = [s for s in params.getlist("status") if s in Order.Status.values]
    if statuses:
        filters["status"] = statuses
    kinds = [k for k in params.getlist("fulfilment") if k in Order.Fulfilment.values]
    if kinds:
        filters["fulfilment"] = kinds
    if params.get("payment") in Payment.Status.values:
        filters["payment"] = params["payment"]
    for key in ("date_from", "date_to"):
        parsed = parse_date(params.get(key) or "")
        if parsed:
            filters[key] = parsed
    q = (params.get("q") or "").strip()
    if q:
        filters["q"] = q[:64]
    return filters


def _order_queryset(filters: dict):
    qs = Order.objects.select_related("user").order_by("-created_at")
    if filters.get("status"):
        qs = qs.filter(status__in=filters["status"])
    if filters.get("fulfilment"):
        qs = qs.filter(fulfilment_kind__in=filters["fulfilment"])
    if filters.get("payment"):
        qs = qs.filter(payments__status=filters["payment"]).distinct()
    if filters.get("date_from"):
        qs = qs.filter(created_at__date__gte=filters["date_from"])
    if filters.get("date_to"):
        qs = qs.filter(created_at__date__lte=filters["date_to"])
    if filters.get("q"):
        qs = qs.filter(Q(order_number__icontains=filters["q"]) | Q(email__icontains=filters["q"]))
    return qs


def order_queue(filters: dict, page) -> Page:
    return Paginator(_order_queryset(filters), ORDER_QUEUE_PAGE_SIZE).get_page(page)


def order_queue_rows(filters: dict) -> Iterator[list]:
    """CSV rows for the current filter set, streamed off a queryset iterator so the export never
    buffers the whole table (the 4.5 MB response cap)."""
    for o in _order_queryset(filters).iterator():
        yield [
            o.order_number,
            o.created_at.isoformat(),
            o.get_status_display(),
            o.get_fulfilment_kind_display(),
            o.email,
            o.subtotal,
            o.discount,
            o.shipping_fee,
            o.total,
            o.coupon_code,
        ]


def order_saved_views(active: str | None) -> list[dict]:
    return [
        {"key": key, "label": preset["label"], "active": key == active}
        for key, preset in ORDER_SAVED_VIEWS.items()
    ]


# ── Design review queue (M8.6) ─────────────────────────────────────────────────
DESIGN_QUEUE_PAGE_SIZE = 40


def design_queue(params, page) -> Page:
    """One page of designs for the review queue. ``submit`` filters by a bound line's Qikink
    submission state (the dashboard's failed-jobs tile); otherwise ``review`` filters by review
    status, defaulting to the flagged designs a moderator actually has to act on."""
    qs = DesignUpload.objects.select_related("user").order_by("-created_at")
    submit = params.get("submit")
    if submit in CustomDesignOrder.SubmitStatus.values:
        qs = qs.filter(
            Q(front_orders__submit_status=submit) | Q(back_orders__submit_status=submit)
        ).distinct()
    else:
        review = params.get("review") or DesignUpload.ReviewStatus.FLAGGED
        if review in DesignUpload.ReviewStatus.values:
            qs = qs.filter(review_status=review)
        elif review != "all":
            qs = qs.filter(review_status=DesignUpload.ReviewStatus.FLAGGED)
    return Paginator(qs, DESIGN_QUEUE_PAGE_SIZE).get_page(page)


# ── Product management (M8.7) ───────────────────────────────────────────────────
PRODUCT_LIST_PAGE_SIZE = 50


def product_admin_list(params, page) -> Page:
    """One page of ordinary products for the management list, with search and an active/archived
    filter. Variants are prefetched so the row can print stock on hand without an extra query."""
    qs = (
        Product.objects.filter(is_custom_blank=False)
        .select_related("category")
        .prefetch_related("variants")
        .order_by("name")
    )
    q = (params.get("q") or "").strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(slug__icontains=q))
    status = params.get("status")
    if status == "archived":
        qs = qs.filter(is_active=False)
    elif status == "active":
        qs = qs.filter(is_active=True)
    return Paginator(qs, PRODUCT_LIST_PAGE_SIZE).get_page(page)
