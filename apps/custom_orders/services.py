"""Custom-order services: the customise flow (surcharge, add-to-cart), the Qikink submission,
and the poll that maps Qikink's status onto the custom shipment.

Two invariants hold the money and fulfilment paths together:

- Submission is idempotent: once ``qikink_order_id`` is set we never resubmit, and the Qikink
  ``order_number`` is our ``idempotency_key`` (<= 15 chars), so a retry cannot create a second
  print job (rebuild/03-architecture.md §6).
- Order status is **derived from shipments**, never set from a Qikink status directly: the poll
  updates the custom ``Shipment`` and calls ``recompute_order_status_from_shipments`` so a mixed
  stock+custom order stays correct (§6)."""

from __future__ import annotations

import logging
from decimal import Decimal
from urllib.parse import urlsplit

from django.conf import settings
from django.utils import timezone

from apps.common import r2
from apps.orders import services as order_services
from apps.orders.models import Order, Shipment

from .models import CustomBlank, CustomDesignOrder, DesignUpload
from .qikink import QikinkClient, QikinkError

logger = logging.getLogger("custom_orders")

# Qikink gives Qikink no webhook, so a signed GET must outlive their fetch window without being
# useful if it leaks: 24 hours (rebuild/03-architecture.md §8).
DESIGN_LINK_TTL = 24 * 60 * 60

# Qikink statuses that mean the custom shipment has left (set shipped_at) or arrived (delivered).
# Everything else ("Printed", "Manifested", ...) is work in progress and touches no timestamp.
_QIKINK_SHIPPED = {"In-Transit", "Exception"}
_QIKINK_DELIVERED = {"Delivered"}
# Terminal for our submission bookkeeping. A refund or a return is a money action handled
# elsewhere (M9), so these only close the Qikink loop; they never move the order by themselves.
_TERMINAL_QIKINK = {"Delivered", "RTO Initiated", "Returned", "Cancelled"}


def design_link(design: DesignUpload | None) -> str:
    """A short-lived signed URL Qikink can fetch the print-ready art from, or empty."""
    if design is None or not design.r2_key_print:
        return ""
    return r2.signed_get_url(design.r2_key_print, DESIGN_LINK_TTL)


def _mockup_link(design: DesignUpload | None) -> str:
    if design is None or not design.r2_key_mockup:
        return ""
    return r2.signed_get_url(design.r2_key_mockup, DESIGN_LINK_TTL)


def _design_entry(design: DesignUpload | None, placement_sku: str, width, height) -> dict:
    return {
        "design_code": placement_sku or "fr",
        "width_inches": str(width),
        "height_inches": str(height),
        "placement_sku": placement_sku,
        "design_link": design_link(design),
        "mockup_link": _mockup_link(design),
    }


def build_order_payload(custom: CustomDesignOrder) -> dict:
    """Assemble the Qikink ``order/create`` body from the paid order snapshot.

    Type traps from rebuild/02-research.md §3: ``quantity``, ``price`` and ``total_order_value``
    are strings, while ``search_from_my_products`` is a number. ``order_number`` is the custom
    line's key, capped at 15 chars. Design and mockup links are 24-hour signed GETs.
    ``shipping_address`` is the buyer's, because Qikink dropships straight to them."""
    order = custom.order
    name_parts = (order.ship_full_name or "").split(" ", 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    designs = [
        _design_entry(
            custom.design_upload, custom.placement_sku, custom.width_inches, custom.height_inches
        )
    ]
    if custom.back_design_upload is not None:
        designs.append(
            _design_entry(
                custom.back_design_upload,
                custom.back_placement_sku,
                custom.back_width_inches,
                custom.back_height_inches,
            )
        )

    line_price = str(order.total)
    return {
        "order_number": custom.idempotency_key,
        "qikink_shipping": "1",
        "gateway": "Prepaid",
        "total_order_value": str(order.total),
        "line_items": [
            {
                "search_from_my_products": 0,
                "quantity": str(custom.quantity),
                "price": line_price,
                "sku": custom.blank_variant.sku if custom.blank_variant else "",
                "print_type_id": custom.print_type_id,
                "designs": designs,
            }
        ],
        "shipping_address": {
            "first_name": first_name,
            "last_name": last_name,
            "address1": order.ship_line1,
            "address2": order.ship_line2,
            "phone": order.phone,
            "email": order.email,
            "city": order.ship_city,
            "province": order.ship_state,
            "zip": order.ship_postal_code,
            "country_code": order.ship_country,
        },
    }


def submit_to_qikink(custom: CustomDesignOrder, *, client: QikinkClient | None = None) -> str:
    """Submit a paid custom order to Qikink. Idempotent and gated on payment and review.

    Returns a short result string. Never raises for the 'already submitted' or 'not
    submittable' cases: those are expected no-ops."""
    if custom.qikink_order_id:
        return "already_submitted"
    if not custom.is_submittable:
        logger.info("Custom order %s not submittable yet", custom.id)
        return "not_submittable"
    if custom.order is None or not custom.order.is_paid:
        return "not_paid"

    client = client or QikinkClient()
    try:
        resp = client.create_order(build_order_payload(custom))
    except QikinkError as exc:
        custom.submit_status = CustomDesignOrder.SubmitStatus.FAILED
        custom.retry_count += 1
        custom.last_error = exc.message[:300]
        custom.save(update_fields=["submit_status", "retry_count", "last_error", "updated_at"])
        raise

    custom.qikink_order_id = str(resp.get("order_id") or resp.get("id") or "")
    custom.qikink_status = "submitted"
    custom.submit_status = CustomDesignOrder.SubmitStatus.SUBMITTED
    custom.submitted_at = timezone.now()
    custom.last_error = ""
    custom.save(
        update_fields=[
            "qikink_order_id",
            "qikink_status",
            "submit_status",
            "submitted_at",
            "last_error",
            "updated_at",
        ]
    )
    # The print job is placed, so work has started: PAID to PROCESSING is a legal, non
    # shipment-derived signal. Shipped/delivered come only from the poll via the shipment (§6).
    _advance_order(custom.order, Order.Status.PROCESSING)
    return "submitted"


def submit_paid_design(custom: CustomDesignOrder) -> str:
    """``submit_to_qikink`` with a Qikink outage downgraded to a logged failure.

    Callers are the payment webhook and the admin retry action, neither of which may be
    rolled back by a third party being unreachable. ``submit_status`` records the
    failure, so the row stays visible for a retry."""
    try:
        return submit_to_qikink(custom)
    except QikinkError as exc:
        logger.warning("Qikink submit failed for %s: %s", custom.id, exc.message)
        return "failed"


def _bound_orders(design: DesignUpload):
    """The custom lines this design is used on, whether as the front or the back artwork."""
    return [*design.front_orders.all(), *design.back_orders.all()]


def review_design(design: DesignUpload, *, approve: bool, reason: str = "") -> DesignUpload:
    """Approve or reject one design (M8.6 back-office and the admin action share this).

    Sets the review status and reason, emails the customer either way, and on approval submits
    any paid line whose review only cleared now (``submit_paid_design`` is idempotent and
    re-checks paid + review state, so a design approved after the webhook's window still ships)."""
    design.review_status = (
        DesignUpload.ReviewStatus.APPROVED if approve else DesignUpload.ReviewStatus.REJECTED
    )
    design.review_reason = reason[:200]
    design.save(update_fields=["review_status", "review_reason", "updated_at"])

    from apps.common.email import send_design_review_email

    send_design_review_email(str(design.id), "approved" if approve else "rejected")
    if approve:
        for custom in _bound_orders(design):
            if custom.order_id and custom.order.is_paid:
                submit_paid_design(custom)
    return design


def resubmit_design(custom: CustomDesignOrder) -> str:
    """Retry a Qikink submission for a paid line that has not reached Qikink (M8.6 and the admin
    action). A no-op for an unpaid or already-submitted line, so it is safe to click twice."""
    if custom.order is not None and custom.order.is_paid and not custom.qikink_order_id:
        return submit_paid_design(custom)
    return "skipped"


def _custom_shipment(order: Order) -> Shipment | None:
    return order.shipments.filter(kind=Shipment.Kind.CUSTOM).first()


def apply_status(
    custom: CustomDesignOrder, qikink_status: str, *, awb: str = "", link: str = ""
) -> None:
    """Record a polled Qikink status onto the custom line and its shipment, then let the order
    status be re-derived from shipments. Never transitions the order directly (§6)."""
    safe_link = link if urlsplit(link).scheme.lower() in {"http", "https"} else ""
    custom.qikink_status = qikink_status
    custom.qikink_last_polled_at = timezone.now()
    if awb:
        custom.tracking_awb = awb
    if safe_link:
        custom.tracking_link = safe_link
    if qikink_status in _TERMINAL_QIKINK:
        custom.submit_status = CustomDesignOrder.SubmitStatus.TERMINAL
    custom.save(
        update_fields=[
            "qikink_status",
            "qikink_last_polled_at",
            "tracking_awb",
            "tracking_link",
            "submit_status",
            "updated_at",
        ]
    )

    if custom.order is None:
        return
    shipment = _custom_shipment(custom.order)
    if shipment is None:
        return

    fields = []
    if awb and not shipment.awb:
        shipment.awb = awb
        fields.append("awb")
    if safe_link and not shipment.tracking_url:
        shipment.tracking_url = safe_link
        fields.append("tracking_url")
    if qikink_status in _QIKINK_SHIPPED or qikink_status in _QIKINK_DELIVERED:
        if shipment.shipped_at is None:
            shipment.shipped_at = timezone.now()
            fields.append("shipped_at")
    if qikink_status in _QIKINK_DELIVERED and shipment.delivered_at is None:
        shipment.delivered_at = timezone.now()
        fields.append("delivered_at")
    if fields:
        shipment.save(update_fields=[*fields, "updated_at"])
        order_services.recompute_order_status_from_shipments(custom.order)


def poll_open_orders(*, queryset=None) -> int:
    """Pull status and tracking for every submitted, non-terminal custom order (or a given
    subset). Qikink has no webhook, so polling is the only source of status and AWB. One
    unreachable order never stops the sweep."""
    open_orders = (
        queryset
        if queryset is not None
        else CustomDesignOrder.objects.filter(
            submit_status=CustomDesignOrder.SubmitStatus.SUBMITTED
        ).exclude(qikink_order_id="")
    )
    client = QikinkClient()
    polled = 0
    for custom in open_orders.select_related("order"):
        try:
            data = client.get_order_status(custom.qikink_order_id)
        except QikinkError:
            continue
        status = data.get("status") or data.get("order_status") or ""
        awb = data.get("awb") or data.get("tracking_id") or ""
        link = data.get("tracking_link") or ""
        if status:
            apply_status(custom, status, awb=awb, link=link)
            polled += 1
    return polled


def sanitise_pending(limit: int = 50) -> int:
    """Sanitise DesignUpload rows left in ``uploaded`` by an interrupted complete call (M7.3
    backstop). The service both `sanitise_designs` and the M8 cron endpoint call, so the sweep
    lives in one place. Returns how many reached ``ready``."""
    from .uploads import sanitise_upload

    pending = DesignUpload.objects.filter(status=DesignUpload.Status.UPLOADED)[:limit]
    return sum(sanitise_upload(design) == "ready" for design in pending)


# On-demand piggyback (§7): poll a single order's custom lines when a customer opens it and its
# last poll is stale. This is what keeps tracking fresh under Hobby's once-a-day cron.
POLL_PIGGYBACK_AGE = timezone.timedelta(minutes=30)


def poll_order_if_stale(order: Order) -> int:
    """Poll this order's open custom lines if none was polled in the last 30 minutes. Safe to
    call from a page render: a Qikink outage is swallowed and simply leaves the data as it was."""
    if not getattr(order, "has_custom_items", False):
        return 0
    open_lines = order.custom_designs.filter(
        submit_status=CustomDesignOrder.SubmitStatus.SUBMITTED
    ).exclude(qikink_order_id="")
    if not open_lines:
        return 0
    freshest = max(
        (c.qikink_last_polled_at for c in open_lines if c.qikink_last_polled_at), default=None
    )
    if freshest is not None and timezone.now() - freshest < POLL_PIGGYBACK_AGE:
        return 0
    try:
        return poll_open_orders(queryset=open_lines)
    except QikinkError:
        return 0


def _advance_order(order: Order, target: str) -> None:
    """Guarded transition: only apply if legal, so out-of-order polls never regress or
    corrupt order state."""
    try:
        order_services.transition(order, target)
    except order_services.OrderError:
        logger.debug("Skipped illegal order transition %s to %s", order.status, target)


# ─── Customise: surcharge and add-to-cart (M7.5, M7.11) ───────────────────────
class CustomOrderError(Exception):
    def __init__(self, message: str, code: str = "custom_order_error"):
        super().__init__(message)
        self.message = message
        self.code = code


def surcharge_for(blank: CustomBlank, width_in, height_in) -> Decimal:
    """The print surcharge for a placement of this size: the smallest tier the art fits in
    (tiers are smallest-first). Falls back to the largest tier when the art fills the area,
    since the tool clamps placement to the printable bounds anyway."""
    tiers = blank.surcharge_tiers or []
    if not tiers:
        return Decimal("0.00")
    width_in, height_in = Decimal(str(width_in)), Decimal(str(height_in))
    for tier in tiers:
        if width_in <= Decimal(str(tier["max_width_in"])) and height_in <= Decimal(
            str(tier["max_height_in"])
        ):
            return Decimal(str(tier["surcharge"]))
    return Decimal(str(tiers[-1]["surcharge"]))


def _check_design(user, design: DesignUpload) -> None:
    if design.user_id != user.id:
        raise CustomOrderError("Unknown design.", code="unknown_design")
    if design.status != DesignUpload.Status.READY:
        raise CustomOrderError("That design is not print-ready yet.", code="design_not_ready")
    if design.review_status == DesignUpload.ReviewStatus.REJECTED:
        raise CustomOrderError("That design was rejected in review.", code="design_rejected")


def add_design_to_cart(
    user,
    *,
    blank: CustomBlank,
    design: DesignUpload,
    size: str,
    color: str,
    placement_sku: str,
    width_inches,
    height_inches,
    quantity: int,
    rights_accepted: bool,
    back: dict | None = None,
) -> CustomDesignOrder:
    """Create a custom line and its cart item. The surcharge and the rights wording are set
    server-side; the client sends neither a price nor the consent text (no dark patterns).

    ``back`` is an optional second placement: ``{design, placement_sku, width_inches,
    height_inches}``. When present its surcharge is added to the front's."""
    from apps.cart.models import Cart, CartItem
    from apps.catalog.models import ProductVariant

    if not rights_accepted:
        raise CustomOrderError(
            "You must accept the rights acknowledgement.", code="rights_required"
        )
    _check_design(user, design)
    if back:
        _check_design(user, back["design"])

    variant = ProductVariant.objects.filter(
        product=blank.product, size=size, color=color, is_active=True
    ).first()
    if variant is None:
        raise CustomOrderError("That size or colour is unavailable.", code="unknown_variant")

    surcharge = surcharge_for(blank, width_inches, height_inches)
    if back:
        surcharge += surcharge_for(blank, back["width_inches"], back["height_inches"])

    custom = CustomDesignOrder.objects.create(
        user=user,
        blank_variant=variant,
        design_upload=design,
        print_type_id=blank.print_type_id,
        placement_sku=placement_sku,
        width_inches=width_inches,
        height_inches=height_inches,
        back_design_upload=back["design"] if back else None,
        back_placement_sku=back["placement_sku"] if back else "",
        back_width_inches=back["width_inches"] if back else None,
        back_height_inches=back["height_inches"] if back else None,
        quantity=quantity,
        print_surcharge=surcharge,
        rights_ack_text=settings.CUSTOM_RIGHTS_TEXT,
    )
    cart, _ = Cart.objects.get_or_create(user=user)
    CartItem.objects.create(cart=cart, variant=variant, quantity=quantity, custom_design=custom)
    return custom
