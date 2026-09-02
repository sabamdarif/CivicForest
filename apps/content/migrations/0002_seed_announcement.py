"""Seed the free-shipping bar, so a fresh database renders the strip the designs show.

The number is content, not a derived value: if `FREE_SHIPPING_THRESHOLD` moves, staff edit
this row. Nothing reads the setting here, so a replay produces the same text everywhere.
"""

from django.db import migrations

TEXT = "FREE SHIPPING ON ALL ORDERS ABOVE ₹999"


def add_bar(apps, schema_editor):
    apps.get_model("content", "AnnouncementBar").objects.get_or_create(
        text=TEXT, defaults={"is_active": True}
    )


def remove_bar(apps, schema_editor):
    apps.get_model("content", "AnnouncementBar").objects.filter(text=TEXT).delete()


class Migration(migrations.Migration):
    dependencies = [("content", "0001_initial")]

    operations = [migrations.RunPython(add_bar, remove_bar)]
