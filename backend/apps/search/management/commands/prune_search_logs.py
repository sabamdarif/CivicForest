from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.search.models import SearchQueryLog


class Command(BaseCommand):
    help = "Delete search analytics logs older than the retention window."

    def add_arguments(self, parser):
        parser.add_argument("--days", type=int, default=90)

    def handle(self, *args, **options):
        days = max(1, options["days"])
        cutoff = timezone.now() - timedelta(days=days)
        deleted, _ = SearchQueryLog.objects.filter(created_at__lt=cutoff).delete()
        self.stdout.write(self.style.SUCCESS(f"Deleted {deleted} search log(s)."))
