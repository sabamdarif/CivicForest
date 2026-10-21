"""Delete carts nobody has touched in thirty days (G6).

M8 mounts `/internal/cron/housekeeping/` on exactly this, with a `JobRun` row around it
(`rebuild/03-architecture.md` §7). Until then it is run by hand.
"""

from django.core.management.base import BaseCommand

from apps.cart import services


class Command(BaseCommand):
    help = "Delete carts nobody has touched in thirty days."

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch",
            type=int,
            default=500,
            help="Stop after this many carts, so one run fits inside the function time limit.",
        )

    def handle(self, *args, **options):
        removed = services.expire_dormant(options["batch"])
        self.stdout.write(self.style.SUCCESS(f"expired {removed} cart(s)"))
