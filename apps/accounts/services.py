"""Account summaries, address invariants, data access, and erasure."""

from __future__ import annotations

import uuid

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Address, DataRequest, User

EXPORT_VERSION = 1
SOCIAL_PROFILE_FIELDS = ("email", "name", "given_name", "family_name", "picture", "locale")


def _iso(value):
    return value.isoformat() if value else None


def _social_profile(data: dict) -> dict:
    return {field: data[field] for field in SOCIAL_PROFILE_FIELDS if field in data}


def _export_cart(cart) -> dict | None:
    if cart is None:
        return None
    return {
        "id": str(cart.pk),
        "created_at": cart.created_at.isoformat(),
        "updated_at": cart.updated_at.isoformat(),
        "items": [
            {
                "id": str(item.pk),
                "variant_sku": item.variant.sku,
                "product": item.variant.product.name,
                "quantity": item.quantity,
                "added_at": item.created_at.isoformat(),
            }
            for item in cart.items.all()
        ],
    }


def _export_order(order) -> dict:
    return {
        "order_number": order.order_number,
        "status": order.status,
        "currency": order.currency,
        "subtotal": str(order.subtotal),
        "discount": str(order.discount),
        "shipping_fee": str(order.shipping_fee),
        "total": str(order.total),
        "coupon_code": order.coupon_code,
        "has_custom_items": order.has_custom_items,
        "created_at": order.created_at.isoformat(),
        "updated_at": order.updated_at.isoformat(),
        "shipping_address": {
            "full_name": order.ship_full_name,
            "phone": order.phone,
            "line1": order.ship_line1,
            "line2": order.ship_line2,
            "city": order.ship_city,
            "state": order.ship_state,
            "postal_code": order.ship_postal_code,
            "country": order.ship_country,
        },
        "items": [
            {
                "product_name": line.product_name,
                "variant_sku": line.variant_sku,
                "size": line.size,
                "color": line.color,
                "unit_price": str(line.unit_price),
                "quantity": line.quantity,
                "line_total": str(line.line_total),
                "is_custom": line.is_custom,
            }
            for line in order.items.all()
        ],
    }


def _export_design(design) -> dict:
    return {
        "id": str(design.pk),
        "order_number": design.order.order_number if design.order_id else None,
        "variant_sku": design.variant.sku if design.variant_id else None,
        "print_type_id": design.print_type_id,
        "placement_sku": design.placement_sku,
        "width_inches": str(design.width_inches),
        "height_inches": str(design.height_inches),
        "quantity": design.quantity,
        "review_status": design.review_status,
        "submit_status": design.submit_status,
        "qikink_order_id": design.qikink_order_id,
        "qikink_status": design.qikink_status,
        "tracking_awb": design.tracking_awb,
        "tracking_link": design.tracking_link,
        "design_file": design.design_file.name or None,
        "mockup_file": design.mockup_file.name or None,
        "created_at": design.created_at.isoformat(),
        "submitted_at": _iso(design.submitted_at),
    }


def _export_authenticator(item) -> dict:
    # Never the `data` column: it holds the TOTP secret and recovery-code values.
    return {
        "type": item.type,
        "created_at": item.created_at.isoformat(),
        "last_used_at": _iso(item.last_used_at),
    }


def dashboard_summary(user: User) -> dict:
    """What the account landing page prints: the last order and how much is saved elsewhere."""
    from apps.cart.models import Wishlist
    from apps.orders.models import Order

    return {
        "latest_order": Order.objects.filter(user=user).prefetch_related("items").first(),
        "order_count": Order.objects.filter(user=user).count(),
        "wishlist_count": Wishlist.objects.filter(user=user).count(),
        "address_count": Address.objects.filter(user=user).count(),
    }


def _lock_user(user: User) -> User:
    return User.objects.select_for_update().get(pk=user.pk)


def _set_default_address(user: User, address: Address) -> None:
    Address.objects.filter(user=user, is_default=True).exclude(pk=address.pk).update(
        is_default=False
    )
    if not address.is_default:
        address.is_default = True
        address.save(update_fields=["is_default"])


@transaction.atomic
def set_default_address(user: User, address: Address) -> None:
    """Promote one address and demote the rest."""
    locked_user = _lock_user(user)
    address = Address.objects.get(pk=address.pk, user=locked_user)
    _set_default_address(locked_user, address)


@transaction.atomic
def save_address(user: User, address: Address) -> Address:
    """Persist an address while keeping one default whenever any address exists."""
    locked_user = _lock_user(user)
    requested_default = address.is_default
    if not address._state.adding:
        previous = Address.objects.filter(pk=address.pk, user=locked_user).first()
        if previous is None:
            raise Address.DoesNotExist
        if previous.is_default and not requested_default:
            requested_default = True

    address.user = locked_user
    address.is_default = False
    address.save()
    has_default = (
        Address.objects.filter(user=locked_user, is_default=True).exclude(pk=address.pk).exists()
    )
    if requested_default or not has_default:
        _set_default_address(locked_user, address)
    return address


@transaction.atomic
def delete_address(user: User, address: Address) -> None:
    """Remove one address, promoting the newest survivor when needed."""
    locked_user = _lock_user(user)
    address = Address.objects.get(pk=address.pk, user=locked_user)
    was_default = address.is_default
    address.delete()
    if was_default:
        replacement = (
            Address.objects.filter(user=locked_user).order_by("-created_at", "-pk").first()
        )
        if replacement:
            _set_default_address(locked_user, replacement)


def security_overview(user: User) -> dict:
    """What is protecting this account, for the hub at /account/security/.

    Every action behind these numbers belongs to an allauth page, so this counts and links
    rather than reimplementing 2FA setup or the session list.
    """
    from allauth.account.models import EmailAddress
    from allauth.mfa.models import Authenticator
    from allauth.mfa.utils import is_mfa_enabled
    from allauth.socialaccount.models import SocialAccount
    from allauth.usersessions.models import UserSession

    addresses = EmailAddress.objects.filter(user=user)
    recovery = Authenticator.objects.filter(
        user=user, type=Authenticator.Type.RECOVERY_CODES
    ).first()
    return {
        "has_password": user.has_usable_password(),
        "email_count": addresses.count(),
        "unverified_count": addresses.filter(verified=False).count(),
        "mfa_enabled": is_mfa_enabled(user),
        "recovery_code_count": len(recovery.wrap().get_unused_codes()) if recovery else 0,
        # purge_and_list drops the sessions that have already expired, so the count is honest.
        "session_count": len(UserSession.objects.purge_and_list(user)),
        "social_count": SocialAccount.objects.filter(user=user).count(),
    }


def export_payload(user: User) -> dict:
    """Return the caller's customer data without reusable credentials."""
    from allauth.account.models import EmailAddress
    from allauth.mfa.models import Authenticator
    from allauth.socialaccount.models import SocialAccount
    from allauth.usersessions.models import UserSession

    from apps.cart.models import Cart, CouponRedemption, Wishlist
    from apps.custom_orders.models import CustomDesignOrder
    from apps.orders.models import Order
    from apps.payments.models import Payment

    orders = Order.objects.filter(user=user).prefetch_related("items")
    order_ids = list(orders.values_list("id", flat=True))
    cart = Cart.objects.filter(user=user).prefetch_related("items__variant__product").first()
    return {
        "export_version": EXPORT_VERSION,
        "exported_at": timezone.now().isoformat(),
        "credentials_omitted": [
            "password hashes",
            "session keys",
            "OAuth tokens and secrets",
            "TOTP secrets",
            "recovery-code values",
            "payment signatures",
            "internal idempotency keys",
        ],
        "account": {
            "id": str(user.pk),
            "email": user.email,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "phone": user.phone,
            "marketing_opt_in": user.marketing_opt_in,
            "is_active": user.is_active,
            "joined": user.date_joined.isoformat(),
            "last_login": _iso(user.last_login),
        },
        "email_addresses": [
            {"email": item.email, "verified": item.verified, "primary": item.primary}
            for item in EmailAddress.objects.filter(user=user)
        ],
        "addresses": [
            {
                "id": str(address.pk),
                "kind": address.kind,
                "full_name": address.full_name,
                "phone": address.phone,
                "line1": address.line1,
                "line2": address.line2,
                "city": address.city,
                "state": address.state,
                "postal_code": address.postal_code,
                "country": address.country,
                "is_default": address.is_default,
                "created_at": address.created_at.isoformat(),
                "updated_at": address.updated_at.isoformat(),
            }
            for address in Address.objects.filter(user=user)
        ],
        "cart": _export_cart(cart),
        "wishlist": [
            {
                "id": str(item.pk),
                "product_id": str(item.product_id),
                "product": item.product.name,
                "slug": item.product.slug,
                "created_at": item.created_at.isoformat(),
            }
            for item in Wishlist.objects.filter(user=user).select_related("product")
        ],
        "orders": [_export_order(order) for order in orders],
        "payments": [
            {
                "id": str(payment.pk),
                "order_number": payment.order.order_number,
                "gateway": payment.gateway,
                "gateway_order_id": payment.gateway_order_id,
                "gateway_payment_id": payment.gateway_payment_id,
                "amount": str(payment.amount),
                "currency": payment.currency,
                "status": payment.status,
                "verified_at": _iso(payment.verified_at),
                "created_at": payment.created_at.isoformat(),
                "updated_at": payment.updated_at.isoformat(),
            }
            for payment in Payment.objects.filter(order_id__in=order_ids).select_related("order")
        ],
        "coupon_redemptions": [
            {
                "coupon": redemption.coupon.code,
                "order_number": redemption.order.order_number,
                "created_at": redemption.created_at.isoformat(),
            }
            for redemption in CouponRedemption.objects.filter(user=user).select_related(
                "coupon", "order"
            )
        ],
        "custom_designs": [
            _export_design(design)
            for design in CustomDesignOrder.objects.filter(user=user).select_related(
                "order", "variant"
            )
        ],
        "data_requests": [
            {
                "id": str(item.pk),
                "kind": item.kind,
                "status": item.status,
                "created_at": item.created_at.isoformat(),
                "updated_at": item.updated_at.isoformat(),
                "handled_at": _iso(item.handled_at),
            }
            for item in DataRequest.objects.filter(user=user)
        ],
        "social_accounts": [
            {
                "provider": account.provider,
                "uid": account.uid,
                "date_joined": account.date_joined.isoformat(),
                "last_login": account.last_login.isoformat(),
                "profile": _social_profile(account.extra_data),
            }
            for account in SocialAccount.objects.filter(user=user)
        ],
        "authenticators": [
            _export_authenticator(item) for item in Authenticator.objects.filter(user=user)
        ],
        "active_sessions": [
            {
                "ip": str(session.ip),
                "user_agent": session.user_agent,
                "created_at": session.created_at.isoformat(),
                "last_seen_at": session.last_seen_at.isoformat(),
            }
            for session in UserSession.objects.purge_and_list(user)
        ],
    }


def request_erasure(user: User) -> tuple[DataRequest, bool]:
    """Create one open erasure request, including when concurrent posts race."""
    existing = DataRequest.objects.filter(
        user=user,
        kind=DataRequest.Kind.ERASURE,
        status=DataRequest.Status.OPEN,
    ).first()
    if existing:
        return existing, False
    try:
        with transaction.atomic():
            return DataRequest.objects.create(user=user, kind=DataRequest.Kind.ERASURE), True
    except IntegrityError:
        return (
            DataRequest.objects.get(
                user=user,
                kind=DataRequest.Kind.ERASURE,
                status=DataRequest.Status.OPEN,
            ),
            False,
        )


@transaction.atomic
def anonymise_account(request: DataRequest, actor: User | None = None) -> bool:
    """Answer an erasure request: strip the account of everything it does not have to keep.

    The customer's own record goes (name, phone, addresses, saved items, email addresses, the
    ability to sign in). Their orders stay, with the name and address snapshotted on them,
    because a sale record is one India requires the seller to retain: DPDP's own exemption for
    a legal obligation is what covers it, and the privacy policy says so.
    """
    from apps.cart.models import Cart, Wishlist

    user = request.user
    user.email = f"erased-{uuid.uuid4().hex[:12]}@civicforest.invalid"
    user.first_name = ""
    user.last_name = ""
    user.phone = ""
    user.marketing_opt_in = False
    user.is_active = False
    user.set_unusable_password()
    user.save()

    user.emailaddress_set.all().delete()
    Address.objects.filter(user=user).delete()
    Wishlist.objects.filter(user=user).delete()
    Cart.objects.filter(user=user).delete()

    request.status = DataRequest.Status.DONE
    request.handled_at = timezone.now()
    request.handled_by = actor
    request.save(update_fields=["status", "handled_at", "handled_by", "updated_at"])
