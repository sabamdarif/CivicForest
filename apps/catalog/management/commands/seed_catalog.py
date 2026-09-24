"""Idempotent catalogue seed: enough real data to judge every storefront page.

Safe to run repeatedly, and it refuses to run outside DEBUG (Q5) so it can never touch a
production catalogue. The category and collection slugs here are the ones the footer links
to, so renaming one means editing `templates/jinja2/_partials/footer.html` too.

Usage: ``python manage.py seed_catalog``
"""

from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.files import File
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.text import slugify

from apps.catalog import services
from apps.catalog.models import (
    Category,
    Collection,
    Color,
    Material,
    Product,
    ProductImage,
    ProductVariant,
    Size,
    SizeChart,
)

SEED_IMAGES = Path(settings.BASE_DIR) / "static" / "img" / "seed"

# (name, blurb, image). Blank image is deliberate: the tiles have a fallback.
CATEGORIES = [
    ("T-Shirts", "Minimal. Comfortable. Made for every day.", "hero-black-tee.png"),
    ("Hoodies", "Warmth meets style. Perfect for all seasons.", "hoodie-green.png"),
    ("Sweatshirts", "Soft, durable and made to last.", "sweatshirt-grey.png"),
    ("Polo Shirts", "Classic looks. Premium feel.", "polo-navy.png"),
    ("Jackets", "Layer up without losing the silhouette.", ""),
    ("Bottoms", "Tailored comfort from waist to hem.", ""),
]

# The five tiles in designs/IMG-20260703-WA0017.jpg, in that order.
COLLECTIONS = [
    ("T-Shirt Collection", "Everyday essentials", "Minimal. Comfortable. Made for every day."),
    ("Hoodie Collection", "Cosy and stylish", "Warmth meets style. Perfect for all seasons."),
    ("Sweatshirt Collection", "Comfort redefined", "Soft, durable and made to last."),
    ("Polo Shirt Collection", "Smart casuals", "Classic looks. Premium feel."),
    ("New Arrivals", "New in", "Discover the latest styles, just added."),
]
COLLECTION_IMAGES = {
    "t-shirt-collection": "hero-black-tee.png",
    "hoodie-collection": "hoodie-green.png",
    "sweatshirt-collection": "sweatshirt-grey.png",
    "polo-shirt-collection": "polo-navy.png",
    "new-arrivals": "rack-new-arrivals.png",
}

MATERIALS = ["Organic Cotton", "Cotton", "Fleece", "Cotton Blend", "French Terry", "Pique Cotton"]

SIZES = [("S", 1), ("M", 2), ("L", 3), ("XL", 4)]
COLORS = [
    ("Black", "#111111", 1),
    ("Forest Green", "#1f3d2b", 2),
    ("Navy", "#1b2a4a", 3),
    ("Beige", "#d8c6a8", 4),
    ("Heather Grey", "#b8b8b8", 5),
    ("White", "#f4f1ea", 6),
    ("Cream", "#efe6d6", 7),
    ("Mocha Brown", "#5b4033", 8),
]

# Seventeen products, so the grid runs to a second page at twelve per page (D6). Two carry an
# MRP, which is the only thing that produces a Sale badge and a strike-through (C2).
PRODUCTS = [
    ("Classic Black Tee", "T-Shirts", "Organic Cotton", 799, None, ["Black", "White"], 180),
    ("Nature Back Print Tee", "T-Shirts", "Organic Cotton", 899, 1099, ["Beige", "Black"], 180),
    ("Signature Navy Tee", "T-Shirts", "Cotton", 799, None, ["Navy", "Black"], 180),
    ("Forest Green Tee", "T-Shirts", "Cotton", 899, None, ["Forest Green"], 190),
    ("Everyday White Tee", "T-Shirts", "Cotton Blend", 699, None, ["White", "Heather Grey"], 160),
    ("Signature Black Hoodie", "Hoodies", "Fleece", 1199, None, ["Black", "Navy"], 320),
    ("Forest Green Hoodie", "Hoodies", "Fleece", 1199, None, ["Forest Green", "Black"], 320),
    ("Classic Beige Hoodie", "Hoodies", "Fleece", 1099, None, ["Beige", "Cream"], 300),
    ("Navy Everyday Hoodie", "Hoodies", "Cotton Blend", 1199, None, ["Navy", "Black"], 300),
    ("Zip-Up Hoodie Cream", "Hoodies", "Fleece", 1274, 1499, ["Cream", "Heather Grey"], 330),
    ("CivicForest Sweatshirt", "Sweatshirts", "French Terry", 1099, None, ["Beige", "Black"], 280),
    ("Heather Grey Sweatshirt", "Sweatshirts", "French Terry", 1099, None, ["Heather Grey"], 280),
    ("Navy Pique Polo", "Polo Shirts", "Pique Cotton", 1099, None, ["Navy", "Black"], 220),
    ("Black Pique Polo", "Polo Shirts", "Pique Cotton", 1099, None, ["Black", "White"], 220),
    ("Everyday Bomber Jacket", "Jackets", "Cotton Blend", 2499, None, ["Black", "Forest Green"], 0),
    ("Tapered Jogger", "Bottoms", "French Terry", 1399, None, ["Black", "Heather Grey"], 260),
    ("Everyday Chino", "Bottoms", "Cotton Blend", 1599, None, ["Beige", "Navy"], 0),
]

PRODUCT_IMAGES = {
    "T-Shirts": "hero-black-tee.png",
    "Hoodies": "hoodie-green.png",
    "Sweatshirts": "sweatshirt-grey.png",
    "Polo Shirts": "polo-navy.png",
    "Jackets": "tee-black-back.png",
    "Bottoms": "rack-new-arrivals.png",
}
BESTSELLERS = {"Signature Black Hoodie", "CivicForest Sweatshirt", "Classic Black Tee"}
COLLECTION_FOR_CATEGORY = {
    "T-Shirts": "T-Shirt Collection",
    "Hoodies": "Hoodie Collection",
    "Sweatshirts": "Sweatshirt Collection",
    "Polo Shirts": "Polo Shirt Collection",
}
# Filled in on a product that already exists but has the field empty, which is what a
# database seeded before these columns did. Booleans are left out: False is a real value.
BACKFILL = (
    "care_instructions",
    "fit_notes",
    "model_note",
    "gsm",
    "weight_grams",
    "length_cm",
    "width_cm",
    "height_cm",
    "meta_title",
    "meta_description",
)
# Stock is uneven on purpose: a struck-through size and a real low-stock line only exist if
# some variants are genuinely empty (E4, J9).
STOCK_CYCLE = [12, 0, 3, 25, 7, 0, 18, 2]

CARE = (
    "Machine wash cold with like colours. Do not bleach. Tumble dry low. "
    "Warm iron on the reverse. Do not iron the print."
)
FIT = "Regular fit. True to size, so take your usual size."
MODEL_NOTE = "Model is 6'1\" and wears size M."

SIZE_CHARTS = {
    "T-Shirts": [
        ["Size", "Chest", "Length", "Shoulder"],
        ["S", "38", "27", "17"],
        ["M", "40", "28", "18"],
        ["L", "42", "29", "19"],
        ["XL", "44", "30", "20"],
    ],
    "Hoodies": [
        ["Size", "Chest", "Length", "Sleeve"],
        ["S", "40", "26", "24"],
        ["M", "42", "27", "25"],
        ["L", "44", "28", "26"],
        ["XL", "46", "29", "27"],
    ],
    "Sweatshirts": [
        ["Size", "Chest", "Length", "Sleeve"],
        ["S", "40", "26", "24"],
        ["M", "42", "27", "25"],
        ["L", "44", "28", "26"],
        ["XL", "46", "29", "27"],
    ],
    "Polo Shirts": [
        ["Size", "Chest", "Length", "Shoulder"],
        ["S", "38", "27", "17"],
        ["M", "40", "28", "18"],
        ["L", "42", "29", "19"],
        ["XL", "44", "30", "20"],
    ],
}


# The custom-print blanks (M7). Each is a hidden catalog product (is_custom_blank) sold only
# through /customise/, plus a CustomBlank config carrying the Qikink mapping, the printable
# areas in inches (with a preview pixel box), and the surcharge tiers (smallest fit first).
CUSTOM_BLANKS = [
    {
        "name": "Custom Tee",
        "slug": "custom-tee",
        "category": "T-Shirts",
        "material": "Cotton",
        "base_price": "699.00",
        "tagline": "Your art on a premium tee.",
        "colours": ["Black", "White"],
        "print_type_id": 1,
        "print_areas": {
            "front": {
                "placement_sku": "fr",
                "max_width_in": 12,
                "max_height_in": 16,
                "px": {"x": 120, "y": 90, "w": 260, "h": 340},
            },
            "back": {
                "placement_sku": "bk",
                "max_width_in": 12,
                "max_height_in": 16,
                "px": {"x": 120, "y": 80, "w": 260, "h": 360},
            },
        },
        "surcharge_tiers": [
            {"max_width_in": 6, "max_height_in": 6, "surcharge": "0.00"},
            {"max_width_in": 10, "max_height_in": 12, "surcharge": "99.00"},
            {"max_width_in": 12, "max_height_in": 16, "surcharge": "199.00"},
        ],
    },
    {
        "name": "Custom Hoodie",
        "slug": "custom-hoodie",
        "category": "Hoodies",
        "material": "Fleece",
        "base_price": "1499.00",
        "tagline": "Your art on a heavyweight hoodie.",
        "colours": ["Black", "Forest Green"],
        "print_type_id": 1,
        "print_areas": {
            "front": {
                "placement_sku": "fr",
                "max_width_in": 12,
                "max_height_in": 14,
                "px": {"x": 130, "y": 120, "w": 240, "h": 280},
            },
            "back": {
                "placement_sku": "bk",
                "max_width_in": 14,
                "max_height_in": 16,
                "px": {"x": 120, "y": 90, "w": 280, "h": 340},
            },
        },
        "surcharge_tiers": [
            {"max_width_in": 6, "max_height_in": 6, "surcharge": "0.00"},
            {"max_width_in": 10, "max_height_in": 12, "surcharge": "149.00"},
            {"max_width_in": 14, "max_height_in": 16, "surcharge": "249.00"},
        ],
    },
]


class Command(BaseCommand):
    help = "Seed categories, collections, materials, size charts and a demo product range."

    @transaction.atomic
    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("seed_catalog refuses to run with DEBUG off (Q5).")

        self._vocabulary()
        categories = self._categories()
        collections = self._collections()
        materials = {
            name: Material.objects.get_or_create(slug=slugify(name), defaults={"name": name})[0]
            for name in MATERIALS
        }
        self._size_charts(categories)

        created = 0
        for offset, (name, category, material, price, mrp, colours, gsm) in enumerate(PRODUCTS):
            product, is_new_row = self._product(
                name, categories[category], materials[material], price, mrp, gsm, offset
            )
            created += is_new_row
            self._variants(product, colours, offset)
            self._collect(product, collections, category, offset)
            self._image(product, PRODUCT_IMAGES.get(category, ""))

        self._custom_blanks(categories, materials)

        # Nothing is findable until a document exists, and the sweep that would build them is
        # M8's cron endpoint, so the seed builds its own.
        call_command("reindex_search", stale=True, batch=Product.objects.count())

        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(categories)} categories, {len(collections)} collections, "
                f"{len(materials)} materials and {created} new products "
                f"({Product.objects.count()} total, {ProductVariant.objects.count()} variants)."
            )
        )

    def _vocabulary(self) -> None:
        for name, order in SIZES:
            Size.objects.get_or_create(name=name, defaults={"display_order": order})
        for name, hex_value, order in COLORS:
            Color.objects.get_or_create(
                name=name, defaults={"hex": hex_value, "display_order": order}
            )

    def _categories(self) -> dict[str, Category]:
        categories = {}
        for order, (name, blurb, image) in enumerate(CATEGORIES):
            category, _ = Category.objects.get_or_create(
                slug=slugify(name),
                defaults={"name": name, "description": blurb, "display_order": order},
            )
            self._attach(category, "image", image)
            categories[name] = category
        return categories

    def _collections(self) -> dict[str, Collection]:
        collections = {}
        for order, (name, tagline, description) in enumerate(COLLECTIONS):
            slug = slugify(name)
            collection, _ = Collection.objects.get_or_create(
                slug=slug,
                defaults={
                    "name": name,
                    "tagline": tagline,
                    "description": description,
                    "display_order": order,
                },
            )
            self._attach(collection, "hero_image", COLLECTION_IMAGES.get(slug, ""))
            collections[name] = collection
        return collections

    def _size_charts(self, categories: dict[str, Category]) -> None:
        for name, rows in SIZE_CHARTS.items():
            SizeChart.objects.get_or_create(
                category=categories[name],
                defaults={
                    "rows": rows,
                    "unit": "in",
                    "notes": "Measured flat, garment not body. Allow half an inch either way.",
                },
            )

    def _product(self, name, category, material, price, mrp, gsm, offset):
        """One product with every legally required field filled in (C10, L9)."""
        base_price = Decimal(price)
        defaults = {
            "name": name,
            "description": (
                f"The {name}, cut for everyday wear and made to keep its shape. "
                "Responsibly sourced fabric, finished in India."
            ),
            "category": category,
            "material": material,
            "base_price": base_price,
            "mrp": Decimal(mrp) if mrp else None,
            "care_instructions": CARE,
            "fit_notes": FIT,
            "model_note": MODEL_NOTE,
            "gsm": gsm or None,
            "weight_grams": 250 + offset * 25,
            "length_cm": Decimal("30.00"),
            "width_cm": Decimal("24.00"),
            "height_cm": Decimal("4.00"),
            "is_bestseller": name in BESTSELLERS,
            "is_new": offset < 4,
            "meta_title": f"{name} | CivicForest Clothing",
            "meta_description": f"Shop the {name} at CivicForest. Free shipping above ₹999.",
        }
        product, created = Product.objects.get_or_create(slug=slugify(name), defaults=defaults)
        if not created:
            empty = {field: defaults[field] for field in BACKFILL if not getattr(product, field)}
            if empty:
                Product.objects.filter(pk=product.pk).update(**empty)
                product.refresh_from_db()
        return product, int(created)

    def _variants(self, product: Product, colours: list[str], offset: int) -> None:
        swatches = dict(Color.objects.values_list("name", "hex"))
        for colour_index, colour in enumerate(colours):
            for size_index, (size, _order) in enumerate(SIZES):
                # Not every product runs to XL, or the size facet would never narrow anything.
                if size == "XL" and offset % 3 == 2:
                    continue
                slot = (offset + colour_index * 2 + size_index) % len(STOCK_CYCLE)
                ProductVariant.objects.get_or_create(
                    product=product,
                    size=size,
                    color=colour,
                    defaults={
                        "color_hex": swatches.get(colour, ""),
                        "stock_quantity": STOCK_CYCLE[slot],
                    },
                )

    def _collect(self, product: Product, collections: dict, category: str, offset: int) -> None:
        """Each product joins its garment collection; the first six also seed New Arrivals, so
        the footer's /collections/new-arrivals/ link lands on something."""
        names = [COLLECTION_FOR_CATEGORY.get(category)]
        if offset < 6:
            names.append("New Arrivals")
        product.collections.add(*[collections[name] for name in names if name in collections])

    def _attach(self, instance, field_name: str, filename: str) -> None:
        """Copy a brand PNG onto an image field, once. Blank stays blank."""
        if not filename or getattr(instance, field_name):
            return
        path = SEED_IMAGES / filename
        if not path.exists():
            return
        with path.open("rb") as handle:
            getattr(instance, field_name).save(filename, File(handle), save=True)

    def _custom_blanks(self, categories: dict, materials: dict) -> None:
        """Seed the custom-print blanks as hidden products (M7). Each rides the ordinary
        variant machinery so cart, stock and fulfilment reuse the catalogue, but is kept out
        of /shop/ by is_custom_blank and exposed only through /customise/."""
        from apps.custom_orders.models import CustomBlank

        for order, blank in enumerate(CUSTOM_BLANKS):
            product, _ = Product.objects.get_or_create(
                slug=slugify(blank["name"]),
                defaults={
                    "name": blank["name"],
                    "description": blank["tagline"],
                    "category": categories[blank["category"]],
                    "material": materials[blank["material"]],
                    "base_price": Decimal(blank["base_price"]),
                    "country_of_origin": "India",
                    "care_instructions": CARE,
                    "is_custom_blank": True,
                },
            )
            if not product.is_custom_blank:
                Product.objects.filter(pk=product.pk).update(is_custom_blank=True)
            self._variants(product, blank["colours"], offset=0)
            CustomBlank.objects.update_or_create(
                product=product,
                defaults={
                    "slug": blank["slug"],
                    "tagline": blank["tagline"],
                    "print_type_id": blank["print_type_id"],
                    "print_areas": blank["print_areas"],
                    "surcharge_tiers": blank["surcharge_tiers"],
                    "display_order": order,
                },
            )

    def _image(self, product: Product, filename: str) -> None:
        if filename and not product.images.exists():
            path = SEED_IMAGES / filename
            if path.exists():
                image = ProductImage(product=product, alt_text=f"{product.name}, front view")
                with path.open("rb") as handle:
                    image.image.save(filename, File(handle), save=True)
        # Also catches rows seeded before the generated widths existed. A row whose file has
        # gone is skipped rather than fatal: one broken record cannot stop the whole seed.
        for image in product.images.filter(width_variants={}):
            if image.image and image.image.storage.exists(image.image.name):
                services.build_image_widths(image)
            else:
                self.stdout.write(self.style.WARNING(f"  missing file for {image.image.name}"))
