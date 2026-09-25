"""Sanitise uploaded designs out of the request path (M7.3 backstop).

A customer's ``complete`` call sanitises their upload inline; this sweep handles any
``DesignUpload`` left in ``uploaded`` by an interrupted call. M8 mounts a cron endpoint on the
same ``services.sanitise_pending``; run by hand otherwise."""

from django.core.management.base import BaseCommand

from apps.custom_orders import services


class Command(BaseCommand):
    help = "Sanitise DesignUpload rows still awaiting processing."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)

    def handle(self, *args, **options):
        done = services.sanitise_pending(options["limit"])
        self.stdout.write(self.style.SUCCESS(f"Sanitised {done} design(s)."))
