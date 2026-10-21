"""Content lookups the templates call. One indexed query per page render, no cache: the
production cache is the database too, so a cached read would cost the same query.

Newsletter opt-in also lives here (J5): a subscribe writes an unconfirmed row and mails a signed
confirm link; only confirming mints the one-time welcome coupon, so applying and walking away
never spends one. The confirm and unsubscribe links carry a ``django.core.signing`` token rather
than a stored secret, so no extra table and no login are needed to act on them."""

from django.core import signing
from django.utils import timezone

from .models import (
    AnnouncementBar,
    ContactMessage,
    FaqEntry,
    HomeSection,
    NewsletterSubscriber,
    Page,
)


def current_announcement() -> AnnouncementBar | None:
    """The bar to render, or None when it is switched off or its window has passed."""
    return AnnouncementBar.objects.live().first()


def home_sections() -> list[HomeSection]:
    """The bands the home page renders, in the order staff put them in."""
    return list(HomeSection.objects.filter(is_active=True))


def get_published_page(slug: str) -> Page | None:
    """A published page by slug, or None. An unpublished or missing slug is a 404 at the view."""
    return Page.objects.filter(slug=slug, is_published=True).first()


def faq_grouped() -> dict[str, list[FaqEntry]]:
    """Active FAQ entries grouped by category in display order, for the accordion and FAQPage
    markup (N3). An entry with no category falls under "General"."""
    groups: dict[str, list[FaqEntry]] = {}
    for entry in FaqEntry.objects.filter(is_active=True):
        groups.setdefault(entry.category or "General", []).append(entry)
    return groups


def record_contact_message(
    *, name: str, email: str, order_number: str, subject: str, message: str
) -> ContactMessage:
    """Store a contact-form message and notify the support inbox (N1). Storing first means a dead
    mail server loses nothing: the message is worked from the back-office inbox regardless."""
    from apps.common.email import send_contact_notification

    msg = ContactMessage.objects.create(
        name=name,
        email=email,
        order_number=order_number,
        subject=subject,
        message=message,
    )
    send_contact_notification(str(msg.pk))
    return msg


# ── Newsletter double opt-in (J5) ─────────────────────────────────────────────
# Separate salts so a confirm link can never be replayed as an unsubscribe or vice versa.
_CONFIRM_SALT = "newsletter:confirm"
_UNSUB_SALT = "newsletter:unsubscribe"
_CONFIRM_MAX_AGE = 60 * 60 * 24 * 7  # a confirm link is good for seven days


def confirm_token(email: str) -> str:
    return signing.dumps(email, salt=_CONFIRM_SALT)


def unsubscribe_token(email: str) -> str:
    return signing.dumps(email, salt=_UNSUB_SALT)


def _read_token(token: str, salt: str, max_age: int | None = None) -> str | None:
    """Return the signed email, or None if the token is tampered, malformed or (for confirm)
    expired. Both link handlers treat None as an invalid link rather than an error."""
    try:
        return signing.loads(token, salt=salt, max_age=max_age)
    except signing.BadSignature:
        return None


def subscribe(email: str, source: str = "") -> NewsletterSubscriber:
    """Record an intent to subscribe and mail a confirm link (double opt-in). Idempotent: an
    already-subscribed address is left alone, so a resubmit cannot spray it with confirm mail."""
    from apps.common.email import send_newsletter_email

    email = email.strip().lower()
    sub, _ = NewsletterSubscriber.objects.get_or_create(email=email, defaults={"source": source})
    if not sub.is_subscribed:
        send_newsletter_email(str(sub.pk), "confirm")
    return sub


def confirm_subscription(token: str) -> NewsletterSubscriber | None:
    """Confirm a subscription from its signed link and, on the first confirmation only, mint the
    single-use welcome coupon and mail it. Returns None for a bad or expired token."""
    from apps.common.email import send_newsletter_email

    email = _read_token(token, _CONFIRM_SALT, _CONFIRM_MAX_AGE)
    if email is None:
        return None
    sub = NewsletterSubscriber.objects.filter(email=email).first()
    if sub is None:
        return None
    first_confirmation = sub.confirmed_at is None
    if first_confirmation:
        sub.confirmed_at = timezone.now()
    sub.unsubscribed_at = None
    sub.save(update_fields=["confirmed_at", "unsubscribed_at", "updated_at"])
    if first_confirmation:
        code = _mint_welcome_coupon()
        send_newsletter_email(str(sub.pk), "welcome", coupon_code=code)
    return sub


def unsubscribe(token: str) -> NewsletterSubscriber | None:
    """One-click unsubscribe from a signed link, no login (J5). Returns None for a bad token."""
    email = _read_token(token, _UNSUB_SALT)
    if email is None:
        return None
    sub = NewsletterSubscriber.objects.filter(email=email).first()
    if sub is None:
        return None
    if sub.unsubscribed_at is None:
        sub.unsubscribed_at = timezone.now()
        sub.save(update_fields=["unsubscribed_at", "updated_at"])
    return sub


def _mint_welcome_coupon() -> str:
    """Create a fresh single-use 10%-off first-order coupon and return its code. Each subscriber
    gets their own code, so a leaked one burns exactly one redemption (J5)."""
    import secrets
    from decimal import Decimal

    from apps.cart.models import Coupon

    code = f"WELCOME{secrets.token_hex(4).upper()}"
    Coupon.objects.create(
        code=code,
        discount_type=Coupon.DiscountType.PERCENT,
        value=Decimal("10"),
        first_order_only=True,
        per_user_limit=1,
        max_uses=1,
    )
    return code
