"""Editable content the storefront renders.

The announcement bar is the whole app today; `Page`, `FaqEntry`, `HomeSection`,
`ContactMessage` and `NewsletterSubscriber` land with M9 (`rebuild/03-architecture.md` §5).
"""

from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from apps.common.models import UUIDTimestampedModel


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
        validators=[
            RegexValidator(r"^(/|https://)", "Use a site path like /shop/ or an https:// link.")
        ],
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
