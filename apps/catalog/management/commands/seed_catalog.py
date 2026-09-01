"""Idempotent catalog seed.

Creates the 5 default categories (plan.md §4) plus materials and a demo product
range drawn from the mockups, attaching brand photography from
``apps/catalog/seed_assets/`` where a matching file exists. Safe to run repeatedly.

Usage: ``python manage.py seed_catalog``
"""

from decimal import Decimal
from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.catalog.models import (
    Category,
    Material,
    Product,
    ProductImage,
    ProductVariant,
)

SEED_ASSETS = Path(__file__).resolve().parents[2] / "seed_assets"

CATEGORIES = [
    ("T-Shirts", "Minimal. Comfortable. Made for every day."),
    ("Hoodies", "Warmth meets style. Perfect for all seasons."),
    ("Sweatshirts", "Soft, durable & made to last."),
    ("Jackets", "Layer up without losing the silhouette."),
    ("Bottoms", "Tailored comfort from waist to hem."),
]

MATERIALS = ["Organic Cotton", "Cotton", "Fleece", "Cotton Blend", "French Terry"]

SIZES = ["S", "M", "L", "XL"]

COLORS = {
    "Black": "#111111",
    "Forest Green": "#1F3D2B",
    "Navy": "#1B2A4A",
    "Beige": "#D8C6A8",
    "Heather Grey": "#B8B8B8",
    "White": "#F4F1EA",
}

# (name, category, material, base_price, [colors], is_new, is_bestseller, image_file)
PRODUCTS = [
    (
        "Classic Black Tee",
        "T-Shirts",
        "Organic Cotton",
        799,
        ["Black", "White"],
        True,
        True,
        "classic-black-tee.png",
    ),
    (
        "Nature Back Print Tee",
        "T-Shirts",
        "Organic Cotton",
        899,
        ["Beige", "Black"],
        True,
        False,
        "nature-back-tee.png",
    ),
    (
        "Signature Navy Tee",
        "T-Shirts",
        "Cotton",
        799,
        ["Navy", "Black"],
        True,
        False,
        "signature-navy.png",
    ),
    (
        "Forest Green Tee",
        "T-Shirts",
        "Cotton",
        899,
        ["Forest Green"],
        True,
        False,
        "signature-green-hoodie.png",
    ),
    (
        "Everyday Navy Tee",
        "T-Shirts",
        "Cotton Blend",
        699,
        ["Navy", "Heather Grey", "White"],
        False,
        True,
        "signature-navy.png",
    ),
    (
        "Minimal Black Hoodie",
        "Hoodies",
        "Fleece",
        1199,
        ["Black", "Navy", "Heather Grey"],
        False,
        True,
        "signature-green-hoodie.png",
    ),
    (
        "Signature Green Hoodie",
        "Hoodies",
        "Fleece",
        1299,
        ["Forest Green", "Black"],
        True,
        False,
        "signature-green-hoodie.png",
    ),
    (
        "Civicforest Sweatshirt",
        "Sweatshirts",
        "French Terry",
        1099,
        ["Beige", "Forest Green", "Black"],
        False,
        True,
        "civicforest-sweatshirt.png",
    ),
    (
        "Heather Grey Sweatshirt",
        "Sweatshirts",
        "French Terry",
        1099,
        ["Heather Grey"],
        False,
        False,
        "civicforest-sweatshirt.png",
    ),
    (
        "Everyday Bomber Jacket",
        "Jackets",
        "Cotton Blend",
        2499,
        ["Black", "Forest Green"],
        True,
        False,
        None,
    ),
    ("Utility Field Jacket", "Jackets", "Cotton", 2799, ["Beige", "Black"], False, False, None),
    (
        "Tapered Jogger",
        "Bottoms",
        "French Terry",
        1399,
        ["Black", "Heather Grey"],
        False,
        True,
        None,
    ),
    ("Everyday Chino", "Bottoms", "Cotton Blend", 1599, ["Beige", "Navy"], False, False, None),
]


class Command(BaseCommand):
    help = "Seed default categories, materials, and a demo product range."

    @transaction.atomic
    def handle(self, *args, **options):
        categories = {}
        for order, (name, desc) in enumerate(CATEGORIES):
            cat, _ = Category.objects.get_or_create(
                slug=slugify(name),
                defaults={"name": name, "description": desc, "display_order": order},
            )
            categories[name] = cat

        materials = {}
        for name in MATERIALS:
            mat, _ = Material.objects.get_or_create(slug=slugify(name), defaults={"name": name})
            materials[name] = mat

        created = 0
        for (
            name,
            category_name,
            material_name,
            price,
            colors,
            is_new,
            is_bestseller,
            image_file,
        ) in PRODUCTS:
            product, was_created = Product.objects.get_or_create(
                slug=slugify(name),
                defaults={
                    "name": name,
                    "description": (
                        f"{name} — elevated everyday wear crafted for comfort, "
                        "designed for confidence. Made from responsibly sourced fabric."
                    ),
                    "category": categories[category_name],
                    "material": materials[material_name],
                    "base_price": Decimal(price),
                    "is_new": is_new,
                    "is_bestseller": is_bestseller,
                    "meta_title": f"{name} | CivicForest",
                    "meta_description": f"Shop the {name} at CivicForest.",
                },
            )
            if was_created:
                created += 1

            self._sync_variants(product, colors)
            self._attach_image(product, image_file)

        self.stdout.write(
            self.style.SUCCESS(
                f"Seed complete: {len(categories)} categories, "
                f"{len(materials)} materials, {created} new products "
                f"({Product.objects.count()} total)."
            )
        )

    def _sync_variants(self, product: Product, colors: list[str]) -> None:
        for color in colors:
            for size in SIZES:
                sku = f"{slugify(product.name)}-{slugify(color)}-{size}".upper()
                ProductVariant.objects.get_or_create(
                    product=product,
                    size=size,
                    color=color,
                    defaults={
                        "sku": sku,
                        "color_hex": COLORS.get(color, ""),
                        "stock_quantity": 25,
                    },
                )

    def _attach_image(self, product: Product, image_file: str | None) -> None:
        if not image_file or product.images.exists():
            return
        path = SEED_ASSETS / image_file
        if not path.exists():
            return
        with path.open("rb") as fh:
            image = ProductImage(product=product, alt_text=product.name)
            image.image.save(image_file, File(fh), save=True)
