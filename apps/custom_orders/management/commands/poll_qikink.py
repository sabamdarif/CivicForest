"""Poll Qikink for status and tracking on open custom shipments (M7.8).

Qikink has no outbound webhook, so this is the sweep that keeps tracking current; the order
page also polls on demand when a customer looks. Wired to cron in M8; run by hand until then."""

from django.core.management.base import BaseCommand

from apps.custom_orders import services


class Command(BaseCommand):
    help = "Poll Qikink for open custom shipments and update tracking."

    def handle(self, *args, **options):
        polled = services.poll_open_orders()
        self.stdout.write(self.style.SUCCESS(f"Polled {polled} custom order(s)."))
