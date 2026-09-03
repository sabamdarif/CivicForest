"""Catalogue read services: what a visitor may see, in what order, and with what counts.

Three things here are load-bearing. ``with_price`` is the same number the card prints, so a
price filter can never hide a product whose card reads less than the ceiling. Facet counts are
computed per group with that group's own selection removed, which is what makes ticking one
size still show how many the other sizes hold (D3). And every multi-valued filter is an
``EXISTS`` rather than a join, so one product stays one row and the pagination count stays
true.
"""

import io
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta
from decimal import Decimal
from pathlib import PurePosixPath
from urllib.parse import urlencode

from django.core.files.base import ContentFile
from django.core.paginator import Page, Paginator
from django.db.models import Count, Exists, F, OuterRef, Prefetch, Q, QuerySet, Subquery, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone
from PIL import Image as PILImage
from PIL import ImageOps

from apps.common.formatting import pct_off, rupees

from .models import (
    Category,
    Collection,
    Color,
    Material,
    Product,
    ProductImage,
    ProductVariant,
    Size,
)

PAGE_SIZE = 12  # D6: four across, three rows
NEW_FOR_DAYS = 30  # C9: the New badge is a window, not a flag staff have to remember to clear
RECENT_COOKIE = "cf_recent"
RECENT_LIMIT = 6  # D10
MAX_FILTER_VALUES = 20  # a hand-edited URL cannot turn into an unbounded IN clause

# P8 wants three widths. WebP only: it has been universal since 2020, so an AVIF and a JPEG
# alongside it would triple the storage and the upload time for nothing.
IMAGE_WIDTHS = (400, 800, 1600)

SLUG = re.compile(r"^[-a-z0-9]{1,90}$")

# Relevance on a page with no search query means featured order: what the shop chose to push,
# then what is newest. M3's results page overrides it with a real rank.
SORTS = {
    "relevance": ("-is_bestseller", "-created_at"),
    "newest": ("-created_at",),
    "price-asc": ("price",),
    "price-desc": ("-price",),
    "popularity": ("-units_sold", "-created_at"),
}
DEFAULT_SORT = "relevance"
SORT_LABELS = {
    "relevance": "Relevance",
    "newest": "Newest first",
    "price-asc": "Price: low to high",
    "price-desc": "Price: high to low",
    "popularity": "Most popular",
}

FILTER_GROUPS = ("category", "size", "color", "material", "collection", "badge", "availability")
BADGE_LABELS = {"new": "New", "sale": "On sale", "bestseller": "Bestseller"}


@dataclass(frozen=True)
class Facet:
    """One filter option and how many products it would leave."""

    value: str
    label: str
    count: int
    selected: bool
    swatch: str = ""


@dataclass(frozen=True)
class Chip:
    """A selected filter and the query string that removes just it."""

    label: str
    query: str


@dataclass(frozen=True)
class Results:
    page: Page
    facets: dict[str, list[Facet]]
    chips: list[Chip] = field(default_factory=list)
    sort: str = DEFAULT_SORT
    query: str = ""


# ── Base querysets ───────────────────────────────────────────────────────────
def active_products() -> QuerySet[Product]:
    """Visible products with everything a card or a detail page reads prefetched.

    Only active variants are prefetched, so ``price_from`` and ``in_stock`` reflect what a
    customer can actually buy. They arrive in the vocabulary's size order rather than
    alphabetically, which is what stops a size row reading L, M, S, XL, and within a size in
    the order staff entered them, so the lead colour on a card is the one they listed first.
    """
    size_rank = Subquery(Size.objects.filter(name=OuterRef("size")).values("display_order")[:1])
    active_variants = (
        ProductVariant.objects.filter(is_active=True)
        .alias(rank=Coalesce(size_rank, Value(999)))
        .order_by("rank", "created_at")
    )
    return (
        Product.objects.filter(is_active=True)
        .select_related("category", "material")
        .prefetch_related(
            "images",
            "tags",
            Prefetch("variants", queryset=active_variants),
        )
    )


def product_by_slug(slug: str) -> Product | None:
    return active_products().filter(slug=slug).first()


def active_categories() -> QuerySet[Category]:
    return Category.objects.filter(is_active=True)


def nav_categories() -> QuerySet[Category]:
    """Top-level categories for the SHOP dropdown (D13), the home tiles and the facet list."""
    return active_categories().filter(parent__isnull=True)


def active_collections() -> QuerySet[Collection]:
    return Collection.objects.filter(is_active=True)


def collection_by_slug(slug: str) -> Collection | None:
    return active_collections().filter(slug=slug).first()


def _listable() -> QuerySet[Product]:
    """The lean base for counting. No prefetches: an aggregate never reads them."""
    return Product.objects.filter(is_active=True)


# ── Price, filters and sorts ─────────────────────────────────────────────────
def with_price(queryset: QuerySet[Product]) -> QuerySet[Product]:
    """Make ``price`` filterable and sortable: the same number the card prints.

    A scalar subquery rather than ``Min()`` over a join, so filtering and ordering go through
    WHERE instead of GROUP BY and the facet aggregates below stay one query each. An alias
    rather than an annotation because nothing selects it: templates read ``price_from`` off
    the variants they already prefetched.
    """
    cheapest = (
        ProductVariant.objects.filter(product=OuterRef("pk"), is_active=True)
        .annotate(sellable=Coalesce("price_override", "product__base_price"))
        .order_by("sellable")
        .values("sellable")[:1]
    )
    return queryset.alias(price=Coalesce(Subquery(cheapest), F("base_price")))


def _variant_exists(*conditions, **lookups) -> Exists:
    """EXISTS instead of a join, so one product stays one row and the page count stays true."""
    return Exists(
        ProductVariant.objects.filter(
            *conditions, product=OuterRef("pk"), is_active=True, **lookups
        )
    )


def _any_iexact(field_name: str, values: list[str]) -> Q:
    """OR of case-insensitive matches: a URL typed as ``size=m`` still matches the stored M."""
    query = Q()
    for value in values:
        query |= Q(**{f"{field_name}__iexact": value})
    return query


def _badge_q(values: list[str]) -> Q:
    """New, On sale and Bestseller are all derived, never stored (C9)."""
    query = Q(pk__in=[])
    if "new" in values:
        query |= Q(is_new=True) | Q(created_at__gte=timezone.now() - timedelta(days=NEW_FOR_DAYS))
    if "sale" in values:
        query |= Q(mrp__isnull=False) & Q(mrp__gt=F("price"))
    if "bestseller" in values:
        query |= Q(is_bestseller=True)
    return query


def _apply(
    queryset: QuerySet[Product], filters: dict, skip: str | None = None
) -> QuerySet[Product]:
    """Every filter except the group named in ``skip``.

    Lifting one group is what lets its own facet counts answer "and how many if I ticked this
    one instead", which is the only reading of D3 that is any use while choosing.
    """
    queryset = with_price(queryset)
    chosen = {group: filters.get(group) or [] for group in FILTER_GROUPS if group != skip}

    if chosen.get("category"):
        queryset = queryset.filter(
            Q(category__slug__in=chosen["category"])
            # One level deep, which is all C8 allows and all the nav exposes.
            | Q(category__parent__slug__in=chosen["category"])
        )
    if chosen.get("material"):
        queryset = queryset.filter(material__slug__in=chosen["material"])
    if chosen.get("size"):
        queryset = queryset.filter(_variant_exists(_any_iexact("size", chosen["size"])))
    if chosen.get("color"):
        queryset = queryset.filter(_variant_exists(_any_iexact("color", chosen["color"])))
    if "in-stock" in chosen.get("availability", []):
        queryset = queryset.filter(_variant_exists(stock_quantity__gt=0))
    if chosen.get("collection"):
        queryset = queryset.filter(
            Exists(
                Collection.objects.filter(
                    products=OuterRef("pk"), is_active=True, slug__in=chosen["collection"]
                )
            )
        )
    if chosen.get("badge"):
        queryset = queryset.filter(_badge_q(chosen["badge"]))
    if skip != "price":
        if filters.get("min_price") is not None:
            queryset = queryset.filter(price__gte=filters["min_price"])
        if filters.get("max_price") is not None:
            queryset = queryset.filter(price__lte=filters["max_price"])
    return queryset


def _units_sold(queryset: QuerySet[Product]) -> QuerySet[Product]:
    """Units sold across paid orders (D4).

    A scalar subquery, not a join annotation: two multi-valued annotations in one query
    multiply each other's rows and the sum comes out wrong. Imported here rather than at
    module level so the catalogue does not carry an orders import it needs for one sort.
    """
    from apps.orders.models import Order, OrderItem

    sold = (
        OrderItem.objects.filter(
            variant__product=OuterRef("pk"), order__status__in=Order.PAID_STATUSES
        )
        .order_by()
        .values("variant__product")
        .annotate(total=Sum("quantity"))
        .values("total")[:1]
    )
    return queryset.alias(units_sold=Coalesce(Subquery(sold), Value(0)))


# ── Reading the query string ─────────────────────────────────────────────────
def _price(raw) -> Decimal | None:
    try:
        value = Decimal(raw)
    except (TypeError, ArithmeticError):
        return None
    return max(value, Decimal(0)) if value.is_finite() else None


def parse_filters(params) -> dict:
    """Whitelist and coerce the query string.

    Unknown keys, junk values and unparseable numbers are dropped rather than rejected: a
    stale or hand-edited URL should widen the result set, never 400. Checkbox groups arrive as
    repeated parameters because that is what a plain form posts.
    """
    filters: dict = {}
    for group in FILTER_GROUPS:
        values = [value.strip() for value in params.getlist(group) if value.strip()]
        if group in {"category", "material", "collection"}:
            values = [v.lower() for v in values if SLUG.match(v.lower())]
        elif group == "badge":
            values = [v for v in values if v in BADGE_LABELS]
        elif group == "availability":
            values = [v for v in values if v == "in-stock"]
        if values:
            filters[group] = list(dict.fromkeys(values))[:MAX_FILTER_VALUES]

    low, high = _price(params.get("min_price")), _price(params.get("max_price"))
    if low is not None and high is not None and low > high:
        low, high = high, low
    filters["min_price"], filters["max_price"] = low, high
    return filters


def parse_sort(raw) -> str:
    return raw if raw in SORTS else DEFAULT_SORT


def query_string(filters: dict, sort: str = DEFAULT_SORT, **extra) -> str:
    """Canonical query string from parsed filters.

    Rebuilt rather than edited, so every link a page emits is normalised whatever the URL
    that produced it looked like, and the default sort never shows up as noise.
    """
    pairs = [(group, value) for group in FILTER_GROUPS for value in (filters.get(group) or [])]
    pairs += [
        (key, filters[key]) for key in ("min_price", "max_price") if filters.get(key) is not None
    ]
    if sort and sort != DEFAULT_SORT:
        pairs.append(("sort", sort))
    pairs += [(key, value) for key, value in extra.items() if value]
    return urlencode(pairs)


# ── Facets (D3) ──────────────────────────────────────────────────────────────
def _chosen(filters: dict, group: str) -> set[str]:
    return {value.lower() for value in filters.get(group) or []}


def _keep(facets: list[Facet]) -> list[Facet]:
    """Drop options that would return nothing, unless they are the ones already ticked: the
    panel should never offer a dead filter, but it must always let you untick."""
    return [facet for facet in facets if facet.count or facet.selected]


def _category_facets(filters: dict) -> list[Facet]:
    counts = dict(
        _apply(_listable(), filters, skip="category")
        .order_by()
        .values_list("category__slug")
        .annotate(total=Count("pk", distinct=True))
    )
    # A product sits in exactly one category, so a parent's count is the sum of its own and
    # its children's, matching what selecting the parent actually returns.
    rolled: dict[str, int] = defaultdict(int)
    for category in active_categories().select_related("parent"):
        parent = category.parent
        rolled[parent.slug if parent else category.slug] += counts.get(category.slug, 0)

    chosen = _chosen(filters, "category")
    return _keep(
        [Facet(c.slug, c.name, rolled.get(c.slug, 0), c.slug in chosen) for c in nav_categories()]
    )


def _variant_facets(filters: dict, attname: str) -> list[Facet]:
    products = _apply(_listable(), filters, skip=attname).values("pk")
    rows = (
        ProductVariant.objects.filter(is_active=True, product__in=products)
        .exclude(**{attname: ""})
        .order_by()
        .values_list(attname)
        .annotate(total=Count("product", distinct=True))
    )
    vocabulary = Size if attname == "size" else Color
    order = dict(vocabulary.objects.values_list("name", "display_order"))
    swatches = (
        {}
        if attname == "size"
        else {name.lower(): hex_ for name, hex_ in Color.objects.values_list("name", "hex")}
    )

    chosen = _chosen(filters, attname)
    counts = dict(rows)
    # A ticked value the other groups now exclude has no row at all, and an option you cannot
    # see is an option you cannot untick. Its canonical spelling comes from the vocabulary.
    canonical = {name.lower(): name for name in order}
    for typed in chosen - {value.lower() for value in counts}:
        counts.setdefault(canonical.get(typed, typed), 0)

    facets = [
        Facet(value, value, total, value.lower() in chosen, swatches.get(value.lower(), ""))
        for value, total in counts.items()
    ]
    # The vocabulary tables carry the order; a value with no row still shows, it just sorts last.
    return _keep(sorted(facets, key=lambda f: (order.get(f.value, 9999), f.value)))


def _related_facets(
    filters: dict, group: str, slug_path: str, name_path: str, model
) -> list[Facet]:
    rows = (
        _apply(_listable(), filters, skip=group)
        .order_by()
        .values_list(slug_path, name_path)
        .annotate(total=Count("pk", distinct=True))
    )
    chosen = _chosen(filters, group)
    found = {slug: (name, total) for slug, name, total in rows if slug}
    # Same reason as above: a ticked option has to stay visible even once it counts nothing.
    for slug, name in model.objects.filter(slug__in=chosen - set(found)).values_list(
        "slug", "name"
    ):
        found[slug] = (name, 0)

    return _keep(
        [
            Facet(slug, name, total, slug in chosen)
            for slug, (name, total) in sorted(found.items(), key=lambda item: item[1][0] or "")
        ]
    )


def _badge_facets(filters: dict) -> list[Facet]:
    """One count per badge, each its own query: the alternative is a filtered aggregate over
    the price alias, which is a lot of subtlety to buy two round trips back."""
    chosen = _chosen(filters, "badge")
    base = _apply(_listable(), filters, skip="badge")
    return _keep(
        [
            Facet(value, label, base.filter(_badge_q([value])).count(), value in chosen)
            for value, label in BADGE_LABELS.items()
        ]
    )


def _availability_facets(filters: dict) -> list[Facet]:
    base = _apply(_listable(), filters, skip="availability")
    count = base.filter(_variant_exists(stock_quantity__gt=0)).count()
    return _keep(
        [Facet("in-stock", "In stock", count, "in-stock" in _chosen(filters, "availability"))]
    )


def facet_counts(filters: dict) -> dict[str, list[Facet]]:
    """Every group's counts, each computed with its own selection lifted (D3)."""
    return {
        "category": _category_facets(filters),
        "size": _variant_facets(filters, "size"),
        "color": _variant_facets(filters, "color"),
        "material": _related_facets(
            filters, "material", "material__slug", "material__name", Material
        ),
        "collection": _related_facets(
            filters, "collection", "collections__slug", "collections__name", Collection
        ),
        "badge": _badge_facets(filters),
        "availability": _availability_facets(filters),
    }


def _price_chip_label(filters: dict) -> str:
    low, high = filters.get("min_price"), filters.get("max_price")
    if low is not None and high is not None:
        return f"{rupees(low, 0)} to {rupees(high, 0)}"
    return f"{rupees(low, 0)} and up" if low is not None else f"Up to {rupees(high, 0)}"


def _chips(filters: dict, facets: dict[str, list[Facet]], sort: str) -> list[Chip]:
    """One chip per selected value, each linking to this page without just that one (D5)."""
    chips = []
    for group, options in facets.items():
        for option in (o for o in options if o.selected):
            remaining = [
                value for value in filters.get(group) or [] if value.lower() != option.value.lower()
            ]
            chips.append(Chip(option.label, query_string({**filters, group: remaining}, sort)))
    if filters.get("min_price") is not None or filters.get("max_price") is not None:
        cleared = {**filters, "min_price": None, "max_price": None}
        chips.append(Chip(_price_chip_label(filters), query_string(cleared, sort)))
    return chips


# ── The listing itself ───────────────────────────────────────────────────────
def product_list(filters: dict, sort: str = DEFAULT_SORT, page=1) -> Results:
    """One page of products, the facet counts, and the chip that undoes each filter."""
    sort = parse_sort(sort)
    queryset = _apply(active_products(), filters)
    if sort == "popularity":
        queryset = _units_sold(queryset)

    paginator = Paginator(queryset.order_by(*SORTS[sort]), PAGE_SIZE)
    facets = facet_counts(filters)
    return Results(
        page=paginator.get_page(page),
        facets=facets,
        chips=_chips(filters, facets, sort),
        sort=sort,
        query=query_string(filters, sort),
    )


def new_arrivals(limit: int = 8) -> QuerySet[Product]:
    """The Just Landed row. Flagged products lead, then newest, so the row is never empty
    just because nobody remembered to tick anything."""
    return active_products().order_by("-is_new", "-created_at")[:limit]


def bestsellers(limit: int = 8) -> QuerySet[Product]:
    return active_products().filter(is_bestseller=True)[:limit]


def related_products(product: Product, limit: int = 4) -> QuerySet[Product]:
    """Same category, newest first, itself excluded (C13). The manual override list is M8's."""
    return (
        active_products()
        .filter(category=product.category)
        .exclude(pk=product.pk)
        .order_by("-is_bestseller", "-created_at")[:limit]
    )


def size_chart_for(product: Product):
    """The chart for the product's category, falling back to its parent's (C11)."""
    category = product.category
    for candidate in (category, category.parent):
        chart = getattr(candidate, "size_chart", None) if candidate else None
        if chart:
            return chart
    return None


# ── What a card and a buy panel print ────────────────────────────────────────
def price_display(product: Product, variant: ProductVariant | None = None):
    """The selling price and the MRP to strike through, or None when there is no discount.

    MRP is product-level; the price is the chosen variant's, or the cheapest one a customer
    could pick. Never returns an MRP at or below the price, so the strike-through and the
    percentage are always a real saving (C2).
    """
    price = variant.effective_price if variant else product.price_from
    mrp = product.mrp if product.mrp and product.mrp > price else None
    return price, mrp


def product_badges(product: Product) -> list[tuple[str, str]]:
    """(label, variant) pairs for the card and the product page.

    Every one is derived from data that already exists (C9): New from the created_at window or
    the staff override, the percentage from the MRP gap, Bestseller set by hand. Nothing here
    may be written by hand, which is what keeps J9's no-invented-urgency rule true by default.
    """
    badges = []
    if product.is_bestseller:
        badges.append(("Bestseller", "bestseller"))
    fresh = product.created_at and product.created_at >= timezone.now() - timedelta(
        days=NEW_FOR_DAYS
    )
    if product.is_new or fresh:
        badges.append(("New", "new"))
    off = pct_off(*price_display(product))
    if off:
        badges.append((f"-{off}%", "sale"))
    return badges


def low_stock_note(variant: ProductVariant, threshold: int) -> str:
    """E4 and J9: a stock message only when the stock is genuinely that low, never a fixture."""
    if variant and 0 < variant.stock_quantity <= threshold:
        return f"Only {variant.stock_quantity} left"
    return ""


def card_data(product: Product) -> dict:
    """Everything ``product_card()`` prints, read off what ``active_products()`` prefetched.

    One place maps a product onto the macro, so the home row, the shop grid, a collection page
    and the related row cannot drift apart, and the macro itself stays free of models.
    """
    image = next(iter(product.images.all()), None)
    price, mrp = price_display(product)
    sizes: list[str] = []
    colours: dict[str, str] = {}
    for variant in product.variants.all():
        if variant.size and variant.size not in sizes:
            sizes.append(variant.size)
        if variant.color and variant.color not in colours:
            colours[variant.color] = variant.color_hex
    lead = next(iter(colours), "")
    return {
        "name": product.name,
        "href": product.get_absolute_url(),
        "image": image.image.url if image else "",
        "srcset": srcset(image) if image else "",
        "alt": (image.alt_text if image else "") or product.name,
        "amount": price,
        "mrp": mrp,
        "meta": " | ".join(part for part in (lead, ", ".join(sizes)) if part),
        "badges": product_badges(product),
        "colours": [(hex_, name) for name, hex_ in colours.items() if hex_],
    }


def recently_viewed(cookie_value: str | None, exclude_slug: str = "") -> list[Product]:
    """The recently-viewed strip (D10), in the order the cookie lists.

    The cookie is written by the browser, so every slug is shape-checked, the list is capped
    before it reaches a query, and anything no longer on sale simply drops out.
    """
    slugs = [
        slug
        for slug in (cookie_value or "").split(",")
        if SLUG.match(slug) and slug != exclude_slug
    ][:RECENT_LIMIT]
    if not slugs:
        return []
    found = {product.slug: product for product in active_products().filter(slug__in=slugs)}
    return [found[slug] for slug in slugs if slug in found]


# ── Images ───────────────────────────────────────────────────────────────────
def build_image_widths(image: ProductImage) -> dict[str, str]:
    """Write the WebP derivatives beside the original and record their storage keys.

    Inline rather than deferred: §7's job system is not built, and a staff member adding a
    handful of photos is not a request worth queueing. Never upscales, so a 900px original
    yields 400 and 800 only and srcset can never promise a file that does not exist.
    """
    field_file = image.image
    if not field_file:
        return {}

    with field_file.open("rb") as handle:
        original = ImageOps.exif_transpose(PILImage.open(handle)).convert("RGB")
    stem = PurePosixPath(field_file.name).with_suffix("")
    targets = [width for width in IMAGE_WIDTHS if width <= original.width] or [original.width]

    keys: dict[str, str] = {}
    for target in targets:
        derivative = original.copy()
        derivative.thumbnail((target, original.height), PILImage.LANCZOS)
        buffer = io.BytesIO()
        derivative.save(buffer, format="WEBP", quality=82, method=6)
        # Deterministic key, deleted first: re-running converges instead of piling up
        # storage-suffixed duplicates.
        key = f"{stem}.{target}.webp"
        if field_file.storage.exists(key):
            field_file.storage.delete(key)
        keys[str(target)] = field_file.storage.save(key, ContentFile(buffer.getvalue()))

    image.width_variants = keys
    image.save(update_fields=["width_variants", "updated_at"])
    return keys


def srcset(image: ProductImage) -> str:
    """``url 400w, url 800w`` from the recorded derivatives, empty when there are none."""
    if not image.width_variants:
        return ""
    storage = image.image.storage
    return ", ".join(
        f"{storage.url(key)} {width}w"
        for width, key in sorted(image.width_variants.items(), key=lambda pair: int(pair[0]))
    )
