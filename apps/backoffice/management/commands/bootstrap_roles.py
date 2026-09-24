"""Create the four back-office roles (O11) as Django groups with explicit permissions.

Reproducible, not hand-clicked: run it after migrations on any environment to get identical
groups. Idempotent, so a later run reconciles membership to the spec here (adding new
permissions, removing ones no longer listed) rather than duplicating anything.

Roles are model-level, which is all Django gives without row filtering:
  Owner       every permission.
  Manager     the whole store, but not staff/user or group administration ("no staff or settings").
  Fulfilment  orders, shipments and stock.
  Support     orders read-only, plus customer messages (and returns once M9 adds the model).

Permission codenames listed here that do not exist yet (e.g. returns, or the M8.13 job models
before their migrations run) are skipped with a note, so the command is safe to run at any point
in M8 and picks the rest up on the next run.
"""

from __future__ import annotations

from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand

# Apps whose permissions make up "the store" a Manager runs. Excludes auth/admin/sessions and the
# allauth internals, so a Manager cannot administer staff, groups or site plumbing.
STORE_APPS = {
    "catalog",
    "cart",
    "orders",
    "payments",
    "custom_orders",
    "content",
    "common",
    "search",
    "accounts",
}

# Fulfilment and Support are narrow, so they are spelled out as "app_label.codename".
FULFILMENT_PERMS = [
    "orders.view_order",
    "orders.change_order",
    "orders.transition_order",
    "orders.view_orderitem",
    "orders.view_shipment",
    "orders.add_shipment",
    "orders.change_shipment",
    "orders.view_statusevent",
    "orders.add_statusevent",
    "common.view_stockadjustment",
    "common.add_stockadjustment",
    "catalog.view_product",
    "catalog.view_productvariant",
    "catalog.change_productvariant",
    "custom_orders.view_customdesignorder",
    "custom_orders.view_designupload",
]

SUPPORT_PERMS = [
    "orders.view_order",
    "orders.view_orderitem",
    "orders.view_shipment",
    "orders.view_statusevent",
    "content.view_contactmessage",
    "content.change_contactmessage",
    # Returns land with M9; listed now so the next run grants them without editing this file.
    "orders.view_returnrequest",
    "orders.change_returnrequest",
]

ROLE_ORDER = ["Owner", "Manager", "Fulfilment", "Support"]


class Command(BaseCommand):
    help = "Create or reconcile the Owner, Manager, Fulfilment and Support groups (O11)."

    def handle(self, *args, **options):
        perms_by_role = {
            "Owner": Permission.objects.all(),
            "Manager": self._manager_perms(),
            "Fulfilment": self._named(FULFILMENT_PERMS),
            "Support": self._named(SUPPORT_PERMS),
        }
        for name in ROLE_ORDER:
            group, created = Group.objects.get_or_create(name=name)
            perms = perms_by_role[name]
            group.permissions.set(perms)
            verb = "created" if created else "reconciled"
            self.stdout.write(self.style.SUCCESS(f"{verb} {name} ({len(perms)} permissions)"))

    def _manager_perms(self):
        qs = Permission.objects.filter(content_type__app_label__in=STORE_APPS)
        # "No staff": a Manager can see customers but not create or alter user rows.
        return list(
            qs.exclude(
                content_type__app_label="accounts",
                content_type__model="user",
                codename__regex=r"^(add|change|delete)_",
            )
        )

    def _named(self, dotted: list[str]) -> list[Permission]:
        found = []
        for dotted_perm in dotted:
            app_label, codename = dotted_perm.split(".", 1)
            perm = Permission.objects.filter(
                content_type__app_label=app_label, codename=codename
            ).first()
            if perm is None:
                self.stdout.write(self.style.WARNING(f"skipped (not migrated yet): {dotted_perm}"))
                continue
            found.append(perm)
        return found
