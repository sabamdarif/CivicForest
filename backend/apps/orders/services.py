"""Order services: creation from a cart, the status state machine, and stock reservation.

All order state lives behind these functions. Views/webhooks orchestrate; they never
mutate ``Order.status`` or stock directly. The state machine rejects illegal jumps
(e.g. shipping an unpaid order) so a bug or a replayed webhook can't corrupt state."""

from __future__ import annotations

from django.db import transaction
from django.db.models import F

from apps.cart import services as cart_services
from apps.catalog.models import ProductVariant

from .models import Order, OrderItem

# Legal forward transitions. Anything not listed raises (plan.md §4 order lifecycle).
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    Order.Status.CREATED: {Order.Status.PAYMENT_PENDING, Order.Status.CANCELLED},
    Order.Status.PAYMENT_PENDING: {Order.Status.PAID, Order.Status.CANCELLED},
    Order.Status.PAID: {Order.Status.PROCESSING, Order.Status.CANCELLED, Order.Status.REFUNDED},
    Order.Status.PROCESSING: {Order.Status.SHIPPED, Order.Status.CANCELLED, Order.Status.REFUNDED},
    Order.Status.SHIPPED: {Order.Status.DELIVERED, Order.Status.REFUNDED},
    Order.Status.DELIVERED: {Order.Status.REFUNDED},
    Order.Status.CANCELLED: set(),
    Order.Status.REFUNDED: set(),
}


class OrderError(Exception):
    def __init__(self, message: str, code: str = "order_error"):
        super().__init__(message)
        self.message = message
        self.code = code


class InsufficientStock(OrderError):
    def __init__(self, message: str = "Insufficient stock to fulfil this order."):
        super().__init__(message, code="insufficient_stock")


@transaction.atomic
def transition(order: Order, to_status: str) -> Order:
    """Move an order to ``to_status`` if the jump is legal, else raise. Idempotent when
    already in the target state. The row is re-read under lock so concurrent callers
    validate against the current database state rather than a stale model instance."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.status == to_status:
        return order
    allowed = _ALLOWED_TRANSITIONS.get(order.status, set())
    if to_status not in allowed:
        raise OrderError(
            f"Cannot move order from {order.status} to {to_status}.",
            code="illegal_transition",
        )
    order.status = to_status
    order.save(update_fields=["status", "updated_at"])

    # Notify on the transitions the customer cares about. Enqueued (not sent inline) so
    # a slow mail server never blocks the status-poll task or webhook.
    kind = {Order.Status.SHIPPED: "shipped", Order.Status.DELIVERED: "delivered"}.get(to_status)
    if kind:
        from apps.common.email import send_order_email

        send_order_email.delay(str(order.pk), kind)
    return order


@transaction.atomic
def create_order_from_cart(user, cart, shipping, *, checkout_key: str | None = None) -> Order:
    """Snapshot a priced cart into a new ``payment_pending`` order.

    ``shipping`` is a validated dict of address fields. The cart is left intact until
    payment is confirmed, so an abandoned payment doesn't lose the customer's cart —
    the cart is cleared in ``fulfil_paid_order``."""
    priced = cart_services.price_cart(cart)
    if priced.item_count == 0:
        raise OrderError("Your cart is empty.", code="empty_cart")

    # Defensive re-check: nothing in the cart may exceed live stock at checkout time.
    for line in priced.lines:
        if line.quantity > line.variant.stock_quantity:
            raise InsufficientStock(
                f"Only {line.variant.stock_quantity} of {line.variant.product.name} left."
            )

    order = Order.objects.create(
        user=user,
        status=Order.Status.PAYMENT_PENDING,
        checkout_key=checkout_key,
        email=user.email,
        phone=shipping.get("phone", ""),
        ship_full_name=shipping["full_name"],
        ship_line1=shipping["line1"],
        ship_line2=shipping.get("line2", ""),
        ship_city=shipping["city"],
        ship_state=shipping["state"],
        ship_postal_code=shipping["postal_code"],
        ship_country=shipping.get("country", "IN"),
        currency=getattr(cart, "currency", "INR") or "INR",
        subtotal=priced.subtotal,
        discount=priced.discount,
        shipping_fee=priced.shipping,
        total=priced.total,
        coupon_code=priced.coupon_code or "",
    )
    OrderItem.objects.bulk_create(
        [
            OrderItem(
                order=order,
                cart_item_id=line.cart_item_id,
                variant=line.variant,
                product_name=line.variant.product.name,
                variant_sku=line.variant.sku,
                size=line.variant.size,
                color=line.variant.color,
                unit_price=line.unit_price,
                quantity=line.quantity,
                line_total=line.line_total,
            )
            for line in priced.lines
        ]
    )
    _attach_custom_designs(user, order, [line.variant.id for line in priced.lines])
    return order


def _attach_custom_designs(user, order: Order, variant_ids: list) -> None:
    """Link the user's pending custom designs for these variants to the new order. This
    is what lets the payment webhook submit them to Qikink, which dropships straight to
    the order's shipping address (qikink_shipping=1)."""
    try:
        from apps.custom_orders.models import CustomDesignOrder
    except ImportError:  # custom_orders app optional
        return

    linked = CustomDesignOrder.objects.filter(
        user=user,
        order__isnull=True,
        submit_status=CustomDesignOrder.SubmitStatus.PENDING_PAYMENT,
        variant_id__in=variant_ids,
    ).update(order=order)
    if linked:
        order.items.filter(variant_id__in=order.custom_designs.values("variant_id")).update(
            is_custom=True
        )
        order.has_custom_items = True
        order.save(update_fields=["has_custom_items", "updated_at"])


@transaction.atomic
def reserve_stock(order: Order) -> None:
    """Atomically decrement stock for every line, locking the variant rows first.

    On Postgres ``select_for_update`` serialises two concurrent confirmations against
    the same last unit, so exactly one succeeds; the other raises ``InsufficientStock``.
    All-or-nothing: if any line can't be satisfied, the transaction rolls back and no
    stock is touched."""
    items = list(order.items.select_related("variant"))
    variant_ids = [i.variant_id for i in items if i.variant_id]
    locked = {
        v.id: v for v in ProductVariant.objects.select_for_update().filter(id__in=variant_ids)
    }
    for item in items:
        if not item.variant_id:
            continue
        variant = locked.get(item.variant_id)
        if variant is None or variant.stock_quantity < item.quantity:
            raise InsufficientStock(
                f"Only {getattr(variant, 'stock_quantity', 0)} of {item.product_name} left."
            )
    for item in items:
        variant = locked.get(item.variant_id) if item.variant_id else None
        if variant is not None:
            variant.stock_quantity -= item.quantity
            variant.save(update_fields=["stock_quantity", "updated_at"])


@transaction.atomic
def fulfil_paid_order(order: Order, cart=None) -> Order | None:
    """Called once, from the verified payment webhook. Reserves stock under row locks,
    marks the order paid, records the coupon use, and clears the customer's cart.

    Returns the paid order only when this call performed the transition. A replayed
    webhook that finds the order already paid returns ``None`` without side effects."""
    order = Order.objects.select_for_update().get(pk=order.pk)
    if order.is_paid:
        return None

    reserve_stock(order)
    order.status = Order.Status.PAID
    order.save(update_fields=["status", "updated_at"])

    if order.coupon_code:
        from django.db.models import Q

        from apps.cart.models import Coupon

        # Conditional increment closes the check-then-increment race: N concurrent
        # checkouts can't collectively exceed max_uses (bugs.md #16). Exceeding it is
        # logged, not raised — money is already captured at this point.
        claimed = Coupon.objects.filter(
            Q(max_uses__isnull=True) | Q(used_count__lt=F("max_uses")),
            code=order.coupon_code,
        ).update(used_count=F("used_count") + 1)
        if not claimed:
            import logging

            logging.getLogger("orders").warning(
                "Coupon %s exceeded max_uses on paid order %s",
                order.coupon_code,
                order.order_number,
            )

    if cart is not None:
        # Delete only the lines this order snapshotted — anything the customer added
        # after checkout stays in the cart (bugs.md #15).
        ordered_cart_item_ids = [i.cart_item_id for i in order.items.all() if i.cart_item_id]
        cart.items.filter(id__in=ordered_cart_item_ids).delete()
        cart.coupon = None
        cart.save(update_fields=["coupon", "updated_at"])

    from apps.common.email import send_order_email

    send_order_email.delay(str(order.pk), "confirmation")
    return order
