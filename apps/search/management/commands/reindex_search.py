"""Rebuild search documents (M3.9).

``--stale`` is the sweep: M8 mounts `/internal/cron/search.reindex/` on exactly this, with a
`JobRun` row around it (`rebuild/03-architecture.md` §7). Until then it is run by hand, and the
admin refreshes the one product a staff member just saved.
"""

from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.search import services

# A document is deleted with its product by the FK, and one belonging to a deactivated product
# is left alone: reactivating it should not need a reindex, and the listing filters on is_active.
STALE = Q(search_document__is_stale=True) | Q(search_document__isnull=True)


class Command(BaseCommand):
    help = "Rebuild search documents, all of them or only the ones marked stale."

    def add_arguments(self, parser):
        parser.add_argument(
            "--stale", action="store_true", help="Only documents marked stale by a catalogue edit."
        )
        parser.add_argument(
            "--batch",
            type=int,
            default=500,
            help="Stop after this many products, so one run fits inside the function time limit.",
        )

    def handle(self, *args, **options):
        products = services.indexable()
        if options["stale"]:
            products = products.filter(STALE)

        built = 0
        for product in products[: options["batch"]]:
            services.refresh(product)
            built += 1
        self.stdout.write(self.style.SUCCESS(f"refreshed {built} search document(s)"))
