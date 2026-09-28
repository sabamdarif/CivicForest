"""Seed the static content pages and starter FAQ entries (M9.5, L1).

Idempotent: it updates the row for each slug rather than duplicating, so it is safe to re-run and
to run on every environment for identical copy. The Returns and Exchanges page states the stock
and the custom policy side by side, and the custom policy reflects Qikink's real terms (defect
only, 7 days, unboxing video, no size swap), never a softer promise (F13, research §3). Contact,
grievance and track-order are their own views, so they are not seeded here.
"""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.content.models import FaqEntry, Page


def _pages() -> list[dict]:
    return [
        {
            "slug": "about",
            "title": "Our story",
            "meta_description": "Premium menswear, made in India.",
            "body": (
                "<p>CivicForest makes elevated everyday menswear in India: considered fabric, a "
                "clean fit and honest pricing. We keep a tight range and make each piece well "
                "rather than chase every trend.</p>"
            ),
        },
        {
            "slug": "sustainability",
            "title": "Sustainability",
            "meta_description": "How we think about fabric, waste and the people who make our "
            "clothes.",
            "body": (
                "<p>We print on demand for custom pieces, so a design is made only once it is "
                "ordered and little is wasted. Our stock range is produced in small batches, and "
                "we choose mills and printers we can stand behind.</p>"
            ),
        },
        {
            "slug": "shipping-delivery",
            "title": "Shipping and delivery",
            "meta_description": "Dispatch times, delivery estimates and shipping charges.",
            "body": (
                f"<p>Orders are dispatched within {settings.DISPATCH_DAYS} working days and "
                f"usually arrive within {settings.DELIVERY_DAYS} working days, depending on your "
                f"pincode.</p><p>Shipping is a flat &#8377;{settings.SHIPPING_FLAT_RATE}, free "
                f"over &#8377;{settings.FREE_SHIPPING_THRESHOLD}. Custom printed items ship "
                "separately from stock items, so a mixed order may arrive in two parcels, each "
                "with its own tracking.</p>"
            ),
        },
        {
            "slug": "size-guide",
            "title": "Size guide",
            "meta_description": "How our sizes run and how to measure.",
            "body": (
                "<p>Each product page carries the size chart for that style. Measure a garment you "
                "already own and lay it flat to compare. If you are between sizes, the fit notes "
                "on the product page say whether that style runs small or large.</p>"
            ),
        },
        {
            "slug": "privacy",
            "title": "Privacy policy",
            "meta_description": "What we collect, why, and your rights over your data.",
            "body": (
                "<p>We collect only what an order needs: your name, contact details and shipping "
                "address, and a record of what you bought. We never sell your data. Marketing "
                "email is opt-in and one-click to leave.</p><p>You can export or delete your data "
                "from your account under Your data. For any privacy question, contact our "
                "grievance officer (see Grievance Redressal).</p>"
            ),
        },
        {
            "slug": "terms",
            "title": "Terms and conditions",
            "meta_description": "The terms you agree to when you shop with us.",
            "body": (
                "<p>Prices are in Indian rupees and shown in full before you pay: the cart and "
                "checkout show the subtotal, any discount and shipping before you commit, and "
                "nothing is added afterwards. Payment is prepaid through our payment partner.</p>"
                "<p>Placing an order is an offer to buy; we confirm it once payment is verified. "
                "We may cancel and refund an order we cannot fulfil.</p>"
            ),
        },
    ]


def _returns_body(window: int) -> str:
    return (
        "<p>We want you to be happy with your order. Two policies apply, depending on the item.</p>"
        "<h2>Stock items</h2>"
        f"<p>Return a stock item within {window} days of delivery for any reason. Once we receive "
        "and inspect it, we refund to your original payment method. Shipping is not refunded "
        "unless the item was defective.</p>"
        "<h2>Custom printed items</h2>"
        f"<p>Custom printed items are made to order, so they can be returned only for a defect, "
        f"damage or a wrong item, within {window} days of delivery. You must keep an unboxing "
        "video and clear photos of the item and its packaging: without the unboxing video a defect "
        "claim cannot be assessed. There is no size swap and no change-of-mind return on custom "
        "items, and items measuring within half an inch of the stated size are not considered "
        "defective.</p>"
        "<p>To start a return, open the order in your account and choose Return an item.</p>"
    )


def _faqs() -> list[dict]:
    return [
        {
            "question": "How long will my order take?",
            "answer": "Most orders arrive within a week. Custom printed items are made to order "
            "and may take a little longer, and they ship separately from stock items.",
            "category": "Orders and delivery",
            "display_order": 0,
        },
        {
            "question": "Can I return a custom printed item?",
            "answer": "Only for a defect, damage or a wrong item, within the return window, and "
            "only with an unboxing video. There is no size swap or change-of-mind return on "
            "custom items.",
            "category": "Returns",
            "display_order": 0,
        },
        {
            "question": "How do I return a stock item?",
            "answer": "Open the order in your account, choose Return an item, pick the lines and a "
            "reason, and submit. We email you once it has been reviewed.",
            "category": "Returns",
            "display_order": 1,
        },
    ]


class Command(BaseCommand):
    help = "Create or update the static content pages and starter FAQ entries (M9.5)."

    def handle(self, *args, **options):
        pages = _pages()
        pages.append(
            {
                "slug": "returns-exchanges",
                "title": "Returns and exchanges",
                "meta_description": "Our return policy for stock and custom items.",
                "body": _returns_body(settings.RETURN_WINDOW_DAYS),
            }
        )
        for page in pages:
            Page.objects.update_or_create(
                slug=page["slug"],
                defaults={
                    "title": page["title"],
                    "body": page["body"],
                    "meta_description": page["meta_description"],
                    "is_published": True,
                },
            )
        faqs = _faqs()
        for faq in faqs:
            FaqEntry.objects.update_or_create(
                question=faq["question"],
                defaults={
                    "answer": faq["answer"],
                    "category": faq["category"],
                    "display_order": faq["display_order"],
                    "is_active": True,
                },
            )
        self.stdout.write(
            self.style.SUCCESS(f"Seeded {len(pages)} pages and {len(faqs)} FAQ entries.")
        )
