"""Seed the five home page bands, so a fresh database renders the page the designs show.

Order and copy are content: staff reorder or switch off a band from the admin rather than
waiting on a deploy. The hero image is left blank on purpose, because the template falls back
to the brand still in `static/img/seed/` until someone uploads a real one.
"""

from django.db import migrations

SECTIONS = [
    {
        "kind": "hero",
        "eyebrow": "Premium quality",
        "title": "Style that speaks",
        "subtitle": "Elevated everyday wear crafted for comfort, designed for confidence.",
        "target": "/shop/",
        "cta_label": "Shop now",
        "display_order": 1,
    },
    {"kind": "trust", "display_order": 2},
    {
        "kind": "categories",
        "eyebrow": "Shop by category",
        "title": "Find your style",
        "display_order": 3,
    },
    {
        "kind": "new_arrivals",
        "eyebrow": "New arrivals",
        "title": "Just landed",
        "target": "/collections/new-arrivals/",
        "cta_label": "View all",
        "display_order": 4,
    },
    # The values band's three items are fixed copy in the template, so this row is order and
    # an on/off switch. Give it a title and a heading appears above them.
    {"kind": "values", "display_order": 5},
]


def add_sections(apps, schema_editor):
    model = apps.get_model("content", "HomeSection")
    for section in SECTIONS:
        model.objects.get_or_create(kind=section["kind"], defaults=section)


def remove_sections(apps, schema_editor):
    kinds = [section["kind"] for section in SECTIONS]
    apps.get_model("content", "HomeSection").objects.filter(kind__in=kinds).delete()


class Migration(migrations.Migration):
    dependencies = [("content", "0003_homesection")]

    operations = [migrations.RunPython(add_sections, remove_sections)]
