import uuid

from django.db import models


class UUIDTimestampedModel(models.Model):
    """Abstract base: UUID primary key + created/updated timestamps.

    UUID pks avoid the enumeration risk of sequential integer ids for anything a
    customer can reference in a URL (plan.md §4).
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["-created_at"]
