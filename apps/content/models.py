"""Editable content the storefront renders.

The announcement bar and the home page sections live here; `Page`, `FaqEntry`,
`ContactMessage` and `NewsletterSubscriber` land with M9 (`rebuild/03-architecture.md` §5).
"""

from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from apps.common.models import UUIDTimestampedModel

# Staff are only semi-trusted here: without this, a javascript: URL typed into the admin
# would be stored XSS on every page that renders the link.
SAFE_LINK = RegexValidator(r"^(/|https://)", "Use a site path like /shop/ or an https:// link.")


class AnnouncementBarQuerySet(models.QuerySet):
    def live(self, now=None):
        """Active, and inside its window if it has one. Either bound may be left open."""
        now = now or timezone.now()
        return self.filter(
            models.Q(starts_at__isnull=True) | models.Q(starts_at__lte=now),
            models.Q(ends_at__isnull=True) | models.Q(ends_at__gte=now),
            is_active=True,
        )


class AnnouncementBar(UUIDTimestampedModel):
    """The strip above the header: text, an optional link and an on/off toggle (D14)."""

    text = models.CharField(max_length=160)
    # Staff are only semi-trusted here: without this, a javascript: URL typed into the
    # admin would be stored XSS on every page of the site.
    url = models.CharField(
        max_length=200,
        blank=True,
        validators=[SAFE_LINK],
        help_text="Optional. Links the whole bar.",
    )
    is_active = models.BooleanField(default=True)
    starts_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Optional. Leave both dates blank to run until switched off.",
    )
    ends_at = models.DateTimeField(null=True, blank=True)

    objects = AnnouncementBarQuerySet.as_manager()

    def __str__(self):
        return self.text


class HomeSection(UUIDTimestampedModel):
    """One band on the home page: which kind, what copy sits above it, whether it is on.

    The row carries the chrome only. What goes inside a band comes from the catalogue, so
    switching one on can never leave a heading hanging over an empty strip. One row per kind,
    because a second Just Landed row would be two of the same thing rather than a choice.
    """

    class Kind(models.TextChoices):
        HERO = "hero", "Hero banner"
        TRUST = "trust", "Trust strip"
        CATEGORIES = "categories", "Shop by category"
        NEW_ARRIVALS = "new_arrivals", "Just landed"
        VALUES = "values", "Brand values"

    kind = models.CharField(max_length=20, choices=Kind.choices, unique=True)
    eyebrow = models.CharField(max_length=60, blank=True)
    title = models.CharField(max_length=120, blank=True)
    subtitle = models.CharField(max_length=255, blank=True)
    image = models.ImageField(upload_to="home/", blank=True)
    target = models.CharField(
        max_length=200, blank=True, validators=[SAFE_LINK], help_text="Where the button goes."
    )
    cta_label = models.CharField(max_length=40, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["display_order"]

    def __str__(self):
        return self.get_kind_display()
