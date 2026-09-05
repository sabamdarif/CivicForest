"""List the carts an abandoned-cart reminder is owed to (G5).

The selection is here so M8 only has to mount `/internal/cron/cart.abandoned/` on it. The send
itself waits for the email subsystem: `common.OutboundEmail` does not exist yet, `common/email.py`
sends plain text only, and G5's one-click unsubscribe needs a signed token and a view that M9's
newsletter needs too. Building either now would mean building both twice.

Until then this is the operator's view of how many carts are being abandoned.
"""

from django.core.management.base import BaseCommand

from apps.cart import services


class Command(BaseCommand):
    help = "List the carts owed an abandoned-cart reminder. Does not send anything yet."

    def add_arguments(self, parser):
        parser.add_argument(
            "--batch",
            type=int,
            default=500,
            help="Stop after this many carts, so one run fits inside the function time limit.",
        )

    def handle(self, *args, **options):
        waiting = list(services.carts_awaiting_reminder()[: options["batch"]])
        for cart in waiting:
            last = f"{cart.last_change:%Y-%m-%d %H:%M}"
            self.stdout.write(f"{cart.user.email}: {cart.lines} line(s), last change {last}")
        self.stdout.write(self.style.SUCCESS(f"{len(waiting)} cart(s) awaiting a reminder"))
