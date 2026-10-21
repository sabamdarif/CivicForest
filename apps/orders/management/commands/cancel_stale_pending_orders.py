"""Cancel orders whose payment was started but never completed within 24 h (task 8, I3).

M8 mounts a cron endpoint on this with a `JobRun` row around it (`rebuild/03-architecture.md`
§7). Until then it is run by hand. No stock is released, because a pending order never reserved
any: stock moves only when payment is verified.
"""

from django.core.management.base import BaseCommand

from apps.orders import services


class Command(BaseCommand):
    help = "Cancel payment-pending orders older than 24 hours and email the customer."

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch",
            type=int,
            default=500,
            help="Stop after this many orders, so one run fits inside the function time limit.",
        )

    def handle(self, *args, **options):
        cancelled = services.cancel_stale_pending_orders(options["batch"])
        self.stdout.write(self.style.SUCCESS(f"cancelled {cancelled} stale pending order(s)"))
