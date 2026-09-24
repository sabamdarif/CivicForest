"""Verify the Qikink integration against the sandbox before go-live (M7.12).

Sandbox and live have separate product databases, so ``search_from_my_products`` must be ``0``
with hand-supplied design fields here: a live dashboard SKU does not exist in sandbox
(rebuild/02-research.md §3). This places one order with a supplied design URL, prints Qikink's
response, and optionally polls it. Real print type IDs and placement SKUs read off your
dashboard's Postman collection go into 02-research.md §3 as you confirm them."""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.custom_orders.qikink import QikinkClient, QikinkError


class Command(BaseCommand):
    help = "Place one Qikink sandbox order with hand-supplied design fields and print the result."

    def add_arguments(self, parser):
        parser.add_argument("--design-url", required=True, help="Publicly fetchable art URL.")
        parser.add_argument("--mockup-url", default="", help="Optional mockup URL.")
        parser.add_argument("--placement", default="fr", help="Placement SKU, e.g. fr or bk.")
        parser.add_argument("--print-type-id", type=int, default=1)
        parser.add_argument("--width", default="12")
        parser.add_argument("--height", default="14")
        parser.add_argument("--sku", default="SANDBOX-TEST")
        parser.add_argument("--price", default="699")
        parser.add_argument("--order-number", default="SBX-CHECK-01", help="<= 15 chars.")
        parser.add_argument("--poll", action="store_true", help="Poll the order after creating it.")

    def handle(self, *args, **opts):
        if not (settings.QIKINK_CLIENT_ID and settings.QIKINK_CLIENT_SECRET):
            raise CommandError("Set QIKINK_CLIENT_ID and QIKINK_CLIENT_SECRET first.")
        if "sandbox" not in settings.QIKINK_BASE_URL:
            self.stderr.write(
                self.style.WARNING(f"QIKINK_BASE_URL is {settings.QIKINK_BASE_URL}, not sandbox.")
            )
        if len(opts["order_number"]) > 15:
            raise CommandError("order-number must be 15 characters or fewer (Qikink cap).")

        payload = {
            "order_number": opts["order_number"],
            "qikink_shipping": "1",
            "gateway": "Prepaid",
            "total_order_value": str(opts["price"]),
            "line_items": [
                {
                    "search_from_my_products": 0,
                    "quantity": "1",
                    "price": str(opts["price"]),
                    "sku": opts["sku"],
                    "print_type_id": opts["print_type_id"],
                    "designs": [
                        {
                            "design_code": opts["order_number"],
                            "width_inches": str(opts["width"]),
                            "height_inches": str(opts["height"]),
                            "placement_sku": opts["placement"],
                            "design_link": opts["design_url"],
                            "mockup_link": opts["mockup_url"],
                        }
                    ],
                }
            ],
            "shipping_address": {
                "first_name": "Sandbox",
                "last_name": "Test",
                "address1": "1 MG Road",
                "address2": "",
                "phone": "9999999999",
                "email": "sandbox@example.com",
                "city": "Bengaluru",
                "zip": "560001",
                "province": "Karnataka",
                "country_code": "IN",
            },
        }

        client = QikinkClient()
        try:
            created = client.create_order(payload)
        except QikinkError as exc:
            raise CommandError(f"Qikink rejected the order: {exc.message}") from exc
        self.stdout.write(self.style.SUCCESS(f"Created: {created}"))

        order_id = str(created.get("order_id") or created.get("id") or "")
        if opts["poll"] and order_id:
            try:
                self.stdout.write(f"Status: {client.get_order_status(order_id)}")
            except QikinkError as exc:
                self.stderr.write(self.style.ERROR(f"Poll failed: {exc.message}"))
