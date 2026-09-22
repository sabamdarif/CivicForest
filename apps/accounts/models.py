import uuid

from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models

from apps.common.models import UUIDTimestampedModel


class UserManager(BaseUserManager):
    """Email-based manager: there is no username field."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("An email address is required.")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """Custom user: UUID pk, email is the login identifier, no username.

    UUID pk keeps user references non-enumerable, and email-as-login matches the allauth
    configuration in `config/settings/base.py` (rebuild/01-decisions.md B1).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None  # removed: email is the identifier
    email = models.EmailField("email address", unique=True)
    phone = models.CharField(max_length=20, blank=True)
    marketing_opt_in = models.BooleanField(
        default=False,
        help_text="Explicit opt-in for marketing email, unticked by default (DPDP Act, J9).",
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        db_table = "accounts_user"
        verbose_name = "user"
        verbose_name_plural = "users"

    def __str__(self):
        return self.email


class Address(UUIDTimestampedModel):
    """A saved shipping/billing address. Always scoped to its owner on read."""

    class Kind(models.TextChoices):
        SHIPPING = "shipping", "Shipping"
        BILLING = "billing", "Billing"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="addresses")
    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.SHIPPING)
    full_name = models.CharField(max_length=120)
    phone = models.CharField(max_length=20)
    line1 = models.CharField(max_length=255)
    line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    postal_code = models.CharField(max_length=16)
    country = models.CharField(max_length=2, default="IN")
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ["-is_default", "-created_at"]
        verbose_name_plural = "addresses"
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(is_default=True),
                name="accounts_one_default_address",
            )
        ]

    def __str__(self):
        return f"{self.full_name}, {self.city} ({self.get_kind_display()})"


class DataRequest(UUIDTimestampedModel):
    """A customer's DPDP request to export or erase their data (B8).

    A row rather than an email to support, because a statutory request must not be lost in an
    inbox: staff work the queue in the admin and the timestamps are the evidence that it was
    answered. An export is served immediately and recorded as already handled; an erasure waits
    for the admin action, which is what keeps it from being an irreversible one-click delete.
    """

    class Kind(models.TextChoices):
        EXPORT = "export", "Export"
        ERASURE = "erasure", "Erasure"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        DONE = "done", "Done"
        REFUSED = "refused", "Refused"

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="data_requests")
    kind = models.CharField(max_length=10, choices=Kind.choices)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OPEN)
    note = models.TextField(blank=True)
    handled_at = models.DateTimeField(null=True, blank=True)
    handled_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.SET_NULL, related_name="+"
    )

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["user"],
                condition=models.Q(kind="erasure", status="open"),
                name="accounts_one_open_erasure",
            )
        ]

    def __str__(self):
        return f"{self.get_kind_display()} for {self.user_id} ({self.status})"
