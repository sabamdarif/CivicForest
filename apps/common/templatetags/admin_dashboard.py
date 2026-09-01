"""Data for the admin index dashboard (templates/admin/dashboard.html)."""

from datetime import timedelta
from decimal import Decimal

from django import template
from django.db.models import Count, Sum
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.catalog.models import ProductVariant
from apps.custom_orders.models import CustomDesignOrder
from apps.orders.models import Order

register = template.Library()

# What "sales" means here: money captured and the order not reversed.
REVENUE_STATUSES = [
    Order.Status.PAID,
    Order.Status.PROCESSING,
    Order.Status.SHIPPED,
    Order.Status.DELIVERED,
]
LOW_STOCK_THRESHOLD = 5


def _inr(value) -> str:
    return f"₹{value:,.0f}"


@register.inclusion_tag("admin/dashboard.html")
def admin_dashboard():
    today = timezone.localdate()
    start = today - timedelta(days=29)

    window = Order.objects.filter(status__in=REVENUE_STATUSES, created_at__date__gte=start)
    by_day = {
        row["day"]: row
        for row in window.annotate(day=TruncDate("created_at"))
        .values("day")
        .annotate(revenue=Sum("total"), count=Count("id"))
        .order_by()
    }
    series = []
    for i in range(30):
        day = start + timedelta(days=i)
        row = by_day.get(day, {})
        series.append(
            {
                "label": f"{day.day} {day.strftime('%b')}",
                "revenue": float(row.get("revenue") or 0),
                "orders": row.get("count") or 0,
            }
        )

    revenue_30d = window.aggregate(total=Sum("total"))["total"] or Decimal("0")
    orders_30d = window.count()
    today_row = by_day.get(today, {})
    status_counts = {
        row["status"]: row["count"]
        for row in Order.objects.values("status").annotate(count=Count("id")).order_by()
    }
    awaiting = status_counts.get(Order.Status.PAID, 0) + status_counts.get(
        Order.Status.PROCESSING, 0
    )
    flagged = CustomDesignOrder.objects.filter(
        review_status=CustomDesignOrder.ReviewStatus.FLAGGED
    ).count()

    return {
        "tiles": [
            ("Revenue, last 30 days", _inr(revenue_30d)),
            ("Revenue today", _inr(today_row.get("revenue") or 0)),
            ("Orders, last 30 days", f"{orders_30d:,}"),
            ("Avg order value", _inr(revenue_30d / orders_30d) if orders_30d else "—"),
            ("Awaiting fulfilment", f"{awaiting:,}"),
            ("Designs flagged for review", f"{flagged:,}"),
        ],
        "series": series,
        "pipeline": [
            {"value": value, "label": label, "count": status_counts.get(value, 0)}
            for value, label in Order.Status.choices
        ],
        "recent_orders": Order.objects.select_related("user")[:10],
        "low_stock": ProductVariant.objects.filter(
            is_active=True, stock_quantity__lte=LOW_STOCK_THRESHOLD
        )
        .select_related("product")
        .order_by("stock_quantity")[:8],
    }
