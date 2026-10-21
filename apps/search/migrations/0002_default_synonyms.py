"""The one synonym group the catalogue cannot do without.

A shop that sells tees has to answer "tshirt", "t-shirt" and "tee" with the same products, so
this row ships rather than waiting for someone to type it into the admin. Everything else is
shop-specific and belongs in the admin (decision 6).
"""

from django.db import migrations

GROUP = ("t-shirt", "tshirt, tshirts, t shirt, tee, tees, t-shirts")


def add(apps, schema_editor):
    apps.get_model("search", "SearchSynonym").objects.get_or_create(
        term=GROUP[0], defaults={"expansion": GROUP[1]}
    )


def remove(apps, schema_editor):
    apps.get_model("search", "SearchSynonym").objects.filter(term=GROUP[0]).delete()


class Migration(migrations.Migration):
    dependencies = [("search", "0001_initial")]

    operations = [migrations.RunPython(add, remove)]
