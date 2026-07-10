from django.db import models

from apps.common.models import UUIDTimestampedModel


class SearchQueryLog(UUIDTimestampedModel):
    """Lightweight analytics: what people searched, how many results, did it convert.

    Feeds ranking tuning and surfaces demand for things not yet stocked (plan.md §7).
    """

    query = models.CharField(max_length=200, db_index=True)
    result_count = models.PositiveIntegerField(default=0)
    engine = models.CharField(max_length=16, default="meili")
    converted = models.BooleanField(default=False)
    session_key = models.CharField(max_length=64, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.query} ({self.result_count})"
