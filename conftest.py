"""Fixtures shared across apps.

The storefront pages that need a catalogue are spread over `apps/catalog` and `apps/content`,
and `apps/common` owns the SEO markup they all emit, so this sits at the root rather than in
any one app's tests.

The catalogue here is deliberately awkward, because the bugs worth catching only show up on
data that is: a product with two variants in one size, a cheapest variant that undercuts its
own product's base price, a stale MRP, and a product in two collections at once.
"""

from decimal import Decimal

import pytest

from apps.catalog.models import (
    Category,
    Collection,
    Color,
    Material,
    Product,
    ProductVariant,
    Size,
)


@pytest.fixture
def catalogue():
    """Two categories, one of them a parent with a child, and four products.

    Deliberately awkward: the hoodie's cheapest variant undercuts its own base price, the
    graphic tee carries an MRP, and one product is in two collections at once.
    """
    Size.objects.get_or_create(name="M", defaults={"display_order": 2})
    Size.objects.get_or_create(name="L", defaults={"display_order": 3})
    Color.objects.get_or_create(name="Black", defaults={"hex": "#111111"})
    Color.objects.get_or_create(name="Beige", defaults={"hex": "#d8c6a8"})

    tees = Category.objects.create(name="T-Shirts", slug="t-shirts", display_order=1)
    graphic = Category.objects.create(name="Graphic Tees", slug="graphic-tees", parent=tees)
    hoodies = Category.objects.create(name="Hoodies", slug="hoodies", display_order=2)
    cotton = Material.objects.create(name="Cotton", slug="cotton")
    fleece = Material.objects.create(name="Fleece", slug="fleece")
    landing = Collection.objects.create(name="New arrivals", slug="new-arrivals")
    staples = Collection.objects.create(name="Staples", slug="staples")

    plain = Product.objects.create(
        name="Plain Tee",
        slug="plain-tee",
        category=tees,
        material=cotton,
        base_price=Decimal("799"),
        hsn_code="61091000",
    )
    ProductVariant.objects.create(
        product=plain, size="M", color="Black", color_hex="#111111", stock_quantity=5
    )
    ProductVariant.objects.create(
        product=plain, size="M", color="Beige", color_hex="#d8c6a8", stock_quantity=4
    )
    ProductVariant.objects.create(
        product=plain, size="L", color="Black", color_hex="#111111", stock_quantity=0
    )
    plain.collections.set([landing, staples])

    printed = Product.objects.create(
        name="Graphic Tee",
        slug="graphic-tee",
        category=graphic,
        material=cotton,
        base_price=Decimal("999"),
        mrp=Decimal("1199"),
        hsn_code="61091000",
        is_bestseller=True,
    )
    ProductVariant.objects.create(product=printed, size="M", color="Beige", stock_quantity=2)

    hoodie = Product.objects.create(
        name="Green Hoodie",
        slug="green-hoodie",
        category=hoodies,
        material=fleece,
        base_price=Decimal("1499"),
        hsn_code="61102000",
    )
    ProductVariant.objects.create(product=hoodie, size="M", color="Black", stock_quantity=0)
    ProductVariant.objects.create(
        product=hoodie, size="L", color="Black", price_override=Decimal("1299"), stock_quantity=3
    )

    hidden = Product.objects.create(
        name="Retired Tee",
        slug="retired-tee",
        category=tees,
        base_price=Decimal("500"),
        is_active=False,
    )
    ProductVariant.objects.create(product=hidden, size="M", color="Black", stock_quantity=9)

    return {"plain": plain, "printed": printed, "hoodie": hoodie, "hidden": hidden}
