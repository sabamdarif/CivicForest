"""Content lookups the templates call. One indexed query per page render, no cache: the
production cache is the database too, so a cached read would cost the same query."""

from .models import AnnouncementBar, ContactMessage, FaqEntry, HomeSection, Page


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
