"""Sanitise uploaded designs out of the request path (M7.3 backstop).

A customer's ``complete`` call sanitises their upload inline; this sweep handles any
``DesignUpload`` left in ``uploaded`` by an interrupted call. Wired to cron in M8; run by hand
until then."""

from django.core.management.base import BaseCommand

from apps.custom_orders.models import DesignUpload
from apps.custom_orders.uploads import sanitise_upload


class Command(BaseCommand):
    help = "Sanitise DesignUpload rows still awaiting processing."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=50)

    def handle(self, *args, **options):
        pending = DesignUpload.objects.filter(status=DesignUpload.Status.UPLOADED)[
            : options["limit"]
        ]
        done = sum(sanitise_upload(design) == "ready" for design in pending)
        self.stdout.write(self.style.SUCCESS(f"Sanitised {done} design(s)."))
