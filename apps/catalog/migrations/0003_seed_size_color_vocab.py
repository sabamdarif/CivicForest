"""Give the Size/Color vocabularies a starting set.

0002 backfilled them from variants that already existed, which leaves a fresh
install empty (migrate runs before any product exists) — and empty tables mean the
variant inline in the admin offers no size or colour to pick, so a newly added
product can never be made buyable. Seed the standard set; it's admin-editable after.
"""

from django.db import migrations

SIZES = [("XS", 2), ("S", 3), ("M", 4), ("L", 5), ("XL", 6), ("XXL", 7)]
COLORS = [
    ("Black", "#111111"),
    ("White", "#F4F1EA"),
    ("Navy", "#1B2A4A"),
    ("Forest Green", "#1F3D2B"),
    ("Beige", "#D8C6A8"),
    ("Heather Grey", "#B8B8B8"),
]


def seed_vocab(apps, schema_editor):
    Size = apps.get_model("catalog", "Size")
    Color = apps.get_model("catalog", "Color")
    for name, position in SIZES:
        Size.objects.get_or_create(name=name, defaults={"display_order": position})
    for position, (name, hex_) in enumerate(COLORS, start=1):
        Color.objects.get_or_create(name=name, defaults={"hex": hex_, "display_order": position})


class Migration(migrations.Migration):
    dependencies = [("catalog", "0002_color_size")]

    operations = [migrations.RunPython(seed_vocab, migrations.RunPython.noop)]
