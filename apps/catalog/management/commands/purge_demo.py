"""Remove the demo catalogue that ``seed_catalog`` creates, so a launch starts clean (M10.11).

The inverse of ``seed_catalog``: it deletes exactly the demo products, custom blanks and the
collections and categories that seed created, keyed off that command's own constants so the two
can never drift. Shared vocabulary (sizes, colours, materials) is left alone, because the real
catalogue reuses it. Unlike ``seed_catalog`` this is not DEBUG gated: its whole point is to run
once against the real database at launch. It is destructive, so it confirms unless ``--noinput``.

Usage: ``python manage.py purge_demo [--dry-run] [--noinput]``
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils.text import slugify

from apps.catalog.models import Category, Collection, Product

from .seed_catalog import CATEGORIES, COLLECTIONS, CUSTOM_BLANKS, PRODUCTS


def _demo_product_slugs() -> set[str]:
    names = [name for name, *_ in PRODUCTS] + [blank["name"] for blank in CUSTOM_BLANKS]
    return {slugify(name) for name in names}


class Command(BaseCommand):
    help = "Delete the demo catalogue seeded by seed_catalog (products, blanks, empty categories)."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Report counts, delete nothing.")
        parser.add_argument("--noinput", action="store_true", help="Skip the confirmation prompt.")

    @transaction.atomic
    def handle(self, *args, **options):
        product_slugs = _demo_product_slugs()
        products = Product.objects.filter(slug__in=product_slugs)
        product_count = products.count()

        if options["dry_run"]:
            self.stdout.write(
                f"Would delete {product_count} demo products and any emptied "
                f"demo categories and collections."
            )
            return

        if not options["noinput"]:
            answer = input(
                f"Delete {product_count} demo products and emptied demo "
                f"categories/collections? [y/N] "
            )
            if answer.strip().lower() not in {"y", "yes"}:
                self.stdout.write("Aborted.")
                return

        products.delete()

        # Only remove a demo category or collection once it holds no products: a real product
        # filed under a reused category must keep that category alive.
        collection_slugs = {slugify(name) for name, *_ in COLLECTIONS}
        collections = Collection.objects.filter(slug__in=collection_slugs, products__isnull=True)
        collection_count = collections.count()
        collections.delete()

        category_slugs = {slugify(name) for name, *_ in CATEGORIES}
        categories = Category.objects.filter(slug__in=category_slugs, products__isnull=True)
        category_count = categories.count()
        categories.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {product_count} demo products, {collection_count} collections and "
                f"{category_count} categories. Remaining products: {Product.objects.count()}."
            )
        )
