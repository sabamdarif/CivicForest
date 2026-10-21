"""Rebuild search documents (M3.9).

``--stale`` is the sweep: M8 mounts `/internal/cron/reindex_search/` on the same
`services.reindex`, with a `JobRun` row around it (`rebuild/03-architecture.md` §7). The admin
refreshes the one product a staff member just saved.
"""

from django.core.management.base import BaseCommand

from apps.search import services


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
        built = services.reindex(stale=options["stale"], batch=options["batch"])
        self.stdout.write(self.style.SUCCESS(f"refreshed {built} search document(s)"))
