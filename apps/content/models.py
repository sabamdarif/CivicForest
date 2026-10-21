"""Editable content the storefront renders.

The announcement bar and the home page sections, plus the static pages, FAQ entries, contact
messages and newsletter subscribers M9 adds (`rebuild/03-architecture.md` §5). Page and FAQ bodies
are staff-authored HTML, so they are sanitised on save (§12): staff are only semi-trusted, and an
unsanitised body would be stored XSS on a page every visitor sees.
"""

from django.conf import settings
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone

from apps.common.models import UUIDTimestampedModel

# Staff are only semi-trusted here: without this, a javascript: URL typed into the admin
# would be stored XSS on every page that renders the link.
SAFE_LINK = RegexValidator(r"^(/|https://)", "Use a site path like /shop/ or an https:// link.")


def sanitise_html(value: str) -> str:
    """Strip anything unsafe from staff-authored HTML, keeping ordinary formatting. nh3 (the
    maintained ammonia binding) drops scripts, event handlers and unknown tags, and confines links
    to safe schemes, so a stored body cannot execute (§12)."""
    import nh3

    return nh3.clean(value or "")


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


class Page(UUIDTimestampedModel):
    """A static content page edited in the back-office (L2), so a policy typo is a save, not a
    redeploy. The body is staff HTML, sanitised on save."""

    slug = models.SlugField(max_length=80, unique=True)
    title = models.CharField(max_length=160)
    body = models.TextField(blank=True)
    meta_title = models.CharField(max_length=180, blank=True)
    meta_description = models.CharField(max_length=300, blank=True)
    is_published = models.BooleanField(default=False)

    class Meta:
        ordering = ["title"]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        self.body = sanitise_html(self.body)
        super().save(*args, **kwargs)


class FaqEntry(UUIDTimestampedModel):
    """One question and answer, grouped by category and rendered as an accordion with FAQPage
    markup (N3). The answer is staff HTML, sanitised on save."""

    question = models.CharField(max_length=255)
    answer = models.TextField()
    category = models.CharField(max_length=80, blank=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["category", "display_order"]

    def __str__(self):
        return self.question

    def save(self, *args, **kwargs):
        self.answer = sanitise_html(self.answer)
        super().save(*args, **kwargs)


class ContactMessage(UUIDTimestampedModel):
    """A message from the contact form (N1), worked from the back-office support inbox (N2). The
    optional order number ties a query to an order without exposing the order to the sender."""

    name = models.CharField(max_length=120)
    email = models.EmailField()
    order_number = models.CharField(max_length=16, blank=True)
    subject = models.CharField(max_length=160)
    message = models.TextField()
    handled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    handled_at = models.DateTimeField(null=True, blank=True)
    internal_note = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.subject} from {self.email}"


class NewsletterSubscriber(UUIDTimestampedModel):
    """A newsletter address with double opt-in (J5): a row exists once someone submits, but only a
    ``confirmed_at`` row is subscribed, and ``unsubscribed_at`` is the one-click opt-out. The
    welcome code is issued only on confirmation, so applying and walking away never spends one."""

    email = models.EmailField(unique=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    source = models.CharField(max_length=40, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.email

    @property
    def is_subscribed(self) -> bool:
        return bool(self.confirmed_at) and not self.unsubscribed_at
