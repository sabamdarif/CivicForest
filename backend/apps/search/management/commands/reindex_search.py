"""Rebuild the Meilisearch index from Postgres. Safe to run any time."""

from django.core.management.base import BaseCommand

from apps.search.tasks import reindex_all


class Command(BaseCommand):
    help = "Full resync of the Meilisearch products index from the database."

    def handle(self, *args, **options):
        count = reindex_all()
        self.stdout.write(self.style.SUCCESS(f"Indexed {count} products."))
