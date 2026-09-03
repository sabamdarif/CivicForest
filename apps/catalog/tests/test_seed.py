"""The seed is what makes every storefront page judgeable, so its promises are tested.

Two of them are load-bearing. The footer already links to four category slugs and one
collection slug, so a seed that names them differently ships dead links. And every seeded
product has to pass the compliance gate, or the demo catalogue is a catalogue that could not
legally go live.

Images are left out on purpose: the command tolerates a missing file, and generating sixty
WebP derivatives to assert on data would make this the slowest test in the suite.
"""

import pytest
from django.core.management import CommandError, call_command

from apps.catalog.management.commands import seed_catalog
from apps.catalog.models import Category, Collection, Product, ProductVariant, SizeChart

pytestmark = pytest.mark.django_db

# templates/jinja2/_partials/footer.html hardcodes these.
FOOTER_CATEGORIES = {"t-shirts", "hoodies", "sweatshirts", "polo-shirts"}
FOOTER_COLLECTION = "new-arrivals"


@pytest.fixture(autouse=True)
def no_imagery(tmp_path, monkeypatch, settings):
    settings.DEBUG = True
    settings.MEDIA_ROOT = tmp_path / "media"
    monkeypatch.setattr(seed_catalog, "SEED_IMAGES", tmp_path / "absent")


def test_it_refuses_to_run_with_debug_off(settings):
    settings.DEBUG = False

    with pytest.raises(CommandError, match="DEBUG"):
        call_command("seed_catalog")

    assert not Product.objects.exists()


def test_it_creates_the_slugs_the_footer_links_to():
    call_command("seed_catalog")

    assert FOOTER_CATEGORIES <= set(Category.objects.values_list("slug", flat=True))
    assert Collection.objects.filter(slug=FOOTER_COLLECTION).exists()
    assert Collection.objects.get(slug=FOOTER_COLLECTION).products.exists()


def test_every_seeded_product_could_legally_go_live():
    call_command("seed_catalog")

    for product in Product.objects.all():
        product.full_clean()


def test_it_leaves_enough_room_for_a_second_page_and_a_real_sale():
    call_command("seed_catalog")

    assert Product.objects.count() > 12, "the grid needs a second page to page through (D6)"
    assert Product.objects.filter(mrp__isnull=False).count() >= 2
    assert ProductVariant.objects.filter(stock_quantity=0).exists(), "a struck-through size"
    assert SizeChart.objects.count() >= 4


def test_running_it_twice_changes_nothing():
    call_command("seed_catalog")
    before = (Product.objects.count(), ProductVariant.objects.count())

    call_command("seed_catalog")

    assert (Product.objects.count(), ProductVariant.objects.count()) == before


def test_it_fills_in_a_field_that_did_not_exist_when_the_row_was_written():
    call_command("seed_catalog")
    product = Product.objects.first()
    Product.objects.filter(pk=product.pk).update(hsn_code="", care_instructions="")

    call_command("seed_catalog")
    product.refresh_from_db()

    assert product.hsn_code and product.care_instructions


def test_it_does_not_overwrite_a_real_edit():
    call_command("seed_catalog")
    product = Product.objects.first()
    Product.objects.filter(pk=product.pk).update(fit_notes="Oversized, size down.")

    call_command("seed_catalog")
    product.refresh_from_db()

    assert product.fit_notes == "Oversized, size down."
