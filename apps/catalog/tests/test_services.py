"""Browse correctness: the filters, the facet counts and the prices the shop is judged on.

The adversarial cases are the ones that look right on a small catalogue and lie on a real one:
a multi-valued filter that joins instead of EXISTS inflates the pagination count, a price
filter that reads `base_price` hides a product whose card shows less, and a facet group that
counts itself always reports the number you just selected.
"""

from datetime import timedelta
from decimal import Decimal

import pytest
from django.http import QueryDict
from django.utils import timezone

from apps.catalog import services
from apps.catalog.models import (
    Product,
)

pytestmark = pytest.mark.django_db


def _query(raw: str = "") -> QueryDict:
    return QueryDict(raw)


def _filters(raw: str = "") -> dict:
    return services.parse_filters(_query(raw))


def _slugs(results: services.Results) -> set[str]:
    return {product.slug for product in results.page.object_list}


def _facet(results: services.Results, group: str, value: str) -> services.Facet | None:
    return next((f for f in results.facets[group] if f.value == value), None)


# ── What is listed at all ────────────────────────────────────────────────────
def test_an_inactive_product_is_not_listed(catalogue):
    assert _slugs(services.product_list(_filters())) == {
        "plain-tee",
        "graphic-tee",
        "green-hoodie",
    }


def test_a_parent_category_includes_its_children(catalogue):
    # C8 allows two levels, and the nav only offers the parent, so it has to reach the child.
    assert _slugs(services.product_list(_filters("category=t-shirts"))) == {
        "plain-tee",
        "graphic-tee",
    }


def test_the_size_filter_keeps_one_row_per_product(catalogue):
    """A join would return the plain tee twice: it has two variants in size M."""
    results = services.product_list(_filters("size=M"))

    assert results.page.paginator.count == 3
    assert len(list(results.page.object_list)) == 3


def test_the_collection_filter_keeps_one_row_per_product(catalogue):
    """Same trap through the many-to-many: the plain tee is in both collections."""
    results = services.product_list(_filters("collection=new-arrivals&collection=staples"))

    assert results.page.paginator.count == 1
    assert _slugs(results) == {"plain-tee"}


def test_a_size_typed_in_lower_case_still_matches(catalogue):
    assert _slugs(services.product_list(_filters("size=l"))) == {"plain-tee", "green-hoodie"}


def test_the_availability_filter_only_leaves_something_buyable(catalogue):
    # The hoodie's M is out of stock but its L is not, so the product is still buyable.
    assert _slugs(services.product_list(_filters("availability=in-stock"))) == {
        "plain-tee",
        "graphic-tee",
        "green-hoodie",
    }


# ── Price ────────────────────────────────────────────────────────────────────
def test_the_price_filter_uses_the_number_the_card_prints(catalogue):
    """The hoodie's base price is 1499 but its cheapest variant sells at 1299, which is what
    the card shows, so a 1300 ceiling must not hide it."""
    assert "green-hoodie" in _slugs(services.product_list(_filters("max_price=1300")))
    assert catalogue["hoodie"].price_from == Decimal("1299")


def test_a_floor_above_everything_returns_nothing(catalogue):
    assert _slugs(services.product_list(_filters("min_price=9999"))) == set()


def test_reversed_price_bounds_are_swapped_rather_than_returning_nothing(catalogue):
    filters = _filters("min_price=2000&max_price=700")

    assert (filters["min_price"], filters["max_price"]) == (Decimal("700"), Decimal("2000"))


def test_price_display_never_reports_a_discount_that_is_not_there(catalogue):
    stale = catalogue["plain"]
    stale.mrp = Decimal("500")  # below the selling price: a stale MRP, not a saving
    stale.save()

    price, mrp = services.price_display(stale)

    assert (price, mrp) == (Decimal("799"), None)


def test_price_display_follows_the_chosen_variant(catalogue):
    hoodie = catalogue["hoodie"]
    cheap = hoodie.variants.get(size="L")

    assert services.price_display(hoodie, cheap)[0] == Decimal("1299")
    assert services.price_display(hoodie, hoodie.variants.get(size="M"))[0] == Decimal("1499")


# ── Facet counts (D3) ────────────────────────────────────────────────────────
def test_a_category_facet_rolls_its_children_up(catalogue):
    results = services.product_list(_filters())

    assert _facet(results, "category", "t-shirts").count == 2
    assert _facet(results, "category", "hoodies").count == 1
    # The child is not offered separately: the nav only exposes the top level.
    assert _facet(results, "category", "graphic-tees") is None


def test_a_group_does_not_count_its_own_selection(catalogue):
    """Ticking M has to keep telling you how many L would give, or the panel is useless."""
    results = services.product_list(_filters("size=M"))

    assert _facet(results, "size", "M").count == 3
    assert _facet(results, "size", "M").selected is True
    assert _facet(results, "size", "L").count == 2
    assert _facet(results, "size", "L").selected is False


def test_a_group_does_count_every_other_selection(catalogue):
    results = services.product_list(_filters("category=hoodies"))

    assert _facet(results, "size", "M").count == 1
    assert _facet(results, "size", "L").count == 1
    assert _facet(results, "material", "cotton") is None, "no hoodie is cotton"
    assert _facet(results, "material", "fleece").count == 1


def test_an_option_that_would_return_nothing_is_not_offered(catalogue):
    results = services.product_list(_filters("category=hoodies"))

    assert _facet(results, "collection", "new-arrivals") is None


def test_a_selected_option_stays_offered_even_at_zero_so_it_can_be_unticked(catalogue):
    results = services.product_list(_filters("category=hoodies&material=cotton"))

    cotton = _facet(results, "material", "cotton")
    assert cotton is not None and cotton.selected and results.page.paginator.count == 0


def test_the_colour_facet_carries_its_swatch(catalogue):
    results = services.product_list(_filters())

    assert _facet(results, "color", "Black").swatch == "#111111"


def test_the_badge_facets_are_derived_not_stored(catalogue):
    results = services.product_list(_filters())

    assert _facet(results, "badge", "sale").count == 1, "only the tee with an MRP gap"
    assert _facet(results, "badge", "bestseller").count == 1
    assert _facet(results, "badge", "new").count == 3, "everything was created just now"


def test_the_sizes_come_back_in_the_vocabulary_order(catalogue):
    results = services.product_list(_filters())

    assert [facet.value for facet in results.facets["size"]] == ["M", "L"]


# ── Sorts (D4) ───────────────────────────────────────────────────────────────
def _ordered(raw_sort: str) -> list[str]:
    results = services.product_list(_filters(), raw_sort)
    return [product.slug for product in results.page.object_list]


def test_price_sorts_run_off_the_price_the_card_shows(catalogue):
    assert _ordered("price-asc") == ["plain-tee", "graphic-tee", "green-hoodie"]
    assert _ordered("price-desc") == ["green-hoodie", "graphic-tee", "plain-tee"]


def test_relevance_puts_what_the_shop_pushes_first(catalogue):
    assert _ordered("relevance")[0] == "graphic-tee", "the only bestseller"


def test_popularity_counts_paid_units_and_ignores_the_rest(catalogue):
    from apps.common.factories import OrderFactory, OrderItemFactory
    from apps.orders.models import Order

    paid = OrderFactory(status=Order.Status.PAID)
    OrderItemFactory(order=paid, variant=catalogue["hoodie"].variants.first(), quantity=2)
    abandoned = OrderFactory(status=Order.Status.PAYMENT_PENDING)
    OrderItemFactory(order=abandoned, variant=catalogue["plain"].variants.first(), quantity=99)

    assert _ordered("popularity")[0] == "green-hoodie"


def test_a_sort_nobody_offers_falls_back_instead_of_failing(catalogue):
    assert services.parse_sort("; drop table") == services.DEFAULT_SORT
    assert services.product_list(_filters(), "; drop table").sort == "relevance"


# ── Reading and rebuilding the query string ──────────────────────────────────
def test_junk_in_the_url_is_dropped_not_rejected():
    filters = _filters("category=NOT+A+SLUG&badge=free&availability=maybe&min_price=abc&nope=1")

    assert filters == {"min_price": None, "max_price": None}


def test_a_repeated_value_is_not_counted_twice_and_the_list_is_capped():
    raw = "&".join(f"size=S{n}" for n in range(30))
    filters = _filters(f"size=M&size=M&{raw}")

    assert filters["size"][:1] == ["M"]
    assert len(filters["size"]) == services.MAX_FILTER_VALUES


def test_the_query_string_a_page_emits_is_canonical():
    filters = _filters("sort=newest&size=M&junk=1&max_price=2499")

    assert services.query_string(filters, "newest") == "size=M&max_price=2499&sort=newest"
    # The default sort is never carried: one canonical URL per result set.
    assert services.query_string(filters) == "size=M&max_price=2499"


def test_a_chip_removes_only_its_own_value(catalogue):
    results = services.product_list(_filters("size=M&size=L&category=hoodies"))
    removals = {chip.label: chip.query for chip in results.chips}

    assert removals["M"] == "category=hoodies&size=L"
    assert removals["Hoodies"] == "size=M&size=L"


def test_a_price_range_gets_one_chip_that_clears_both_ends(catalogue):
    results = services.product_list(_filters("min_price=800&max_price=1400"))
    chip = results.chips[-1]

    assert chip.label == "₹800 to ₹1,400"
    assert chip.query == ""


def test_a_page_past_the_end_lands_on_the_last_one(catalogue):
    results = services.product_list(_filters(), page=99)

    assert results.page.number == results.page.paginator.num_pages


# ── Badges, stock and the strip (C9, E4, D10) ────────────────────────────────
def _age(product: Product, days: int) -> Product:
    stale = timezone.now() - timedelta(days=days)
    Product.objects.filter(pk=product.pk).update(created_at=stale)
    return Product.objects.get(pk=product.pk)


def test_the_new_badge_expires_on_its_own(catalogue):
    fresh = catalogue["plain"]
    assert ("New", "new") in services.product_badges(fresh)

    old = _age(fresh, services.NEW_FOR_DAYS + 1)

    assert ("New", "new") not in services.product_badges(old)


def test_a_staff_flag_keeps_the_new_badge_past_the_window(catalogue):
    old = _age(catalogue["plain"], services.NEW_FOR_DAYS + 1)
    old.is_new = True

    assert ("New", "new") in services.product_badges(old)


def test_the_discount_badge_is_computed_and_rounded_down(catalogue):
    # 1199 down to 999 is 16.68%, and an advertised discount must never exceed the real one.
    assert ("-16%", "sale") in services.product_badges(catalogue["printed"])


def test_no_discount_badge_without_a_real_gap(catalogue):
    variants = [badge for _, badge in services.product_badges(catalogue["plain"])]

    assert "sale" not in variants


def test_a_stock_message_appears_only_when_the_stock_is_really_that_low(catalogue):
    hoodie = catalogue["hoodie"]
    low, gone = hoodie.variants.get(size="L"), hoodie.variants.get(size="M")

    assert services.low_stock_note(low, threshold=5) == "Only 3 left"
    assert services.low_stock_note(low, threshold=2) == ""
    assert services.low_stock_note(gone, threshold=5) == "", "out of stock is not low stock"


def test_the_recently_viewed_strip_keeps_the_cookie_order_and_drops_the_rest(catalogue):
    cookie = "green-hoodie,../../etc/passwd,retired-tee,plain-tee,ghost-tee"

    strip = services.recently_viewed(cookie)

    assert [product.slug for product in strip] == ["green-hoodie", "plain-tee"]


def test_the_strip_never_shows_the_page_you_are_on(catalogue):
    strip = services.recently_viewed("plain-tee,green-hoodie", exclude_slug="plain-tee")

    assert [product.slug for product in strip] == ["green-hoodie"]


def test_related_products_leave_out_the_product_itself_and_anything_retired(catalogue):
    Product.objects.create(
        name="Second Tee",
        slug="second-tee",
        category=catalogue["plain"].category,
        base_price=Decimal("899"),
        hsn_code="61091000",
    )

    related = services.related_products(catalogue["plain"])

    assert {product.slug for product in related} == {"second-tee"}


# ── What a card prints ───────────────────────────────────────────────────────
def test_a_card_reads_sizes_in_vocabulary_order_and_the_lead_colour_staff_listed_first(catalogue):
    data = services.card_data(services.product_by_slug("plain-tee"))

    assert data["meta"] == "Black | M, L", "vocabulary order, not the alphabet's L before M"
    assert [name for _hex, name in data["colours"]] == ["Black", "Beige"]
    assert data["href"] == "/product/plain-tee/"


def test_a_card_still_renders_before_anyone_uploads_a_photograph(catalogue):
    data = services.card_data(services.product_by_slug("green-hoodie"))

    assert (data["image"], data["srcset"]) == ("", "")
    assert data["alt"] == "Green Hoodie", "the name stands in, never an empty alt"
    assert data["colours"] == [], "a variant with no hex contributes no swatch, not a black one"
