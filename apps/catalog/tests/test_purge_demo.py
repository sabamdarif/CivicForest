"""purge_demo is the inverse of seed_catalog, so the round trip is what the test asserts:
seed, then purge, and only the demo rows are gone. A real product filed under a reused demo
category must survive, along with that category.
"""

from decimal import Decimal

import pytest
from django.core.management import call_command

from apps.catalog.management.commands import seed_catalog
from apps.catalog.models import Category, Collection, Product

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def no_imagery(tmp_path, monkeypatch, settings):
    settings.DEBUG = True
    settings.MEDIA_ROOT = tmp_path / "media"
    monkeypatch.setattr(seed_catalog, "SEED_IMAGES", tmp_path / "absent")


def test_purge_removes_demo_data_but_keeps_real_products():
    call_command("seed_catalog")
    assert Product.objects.filter(slug="classic-black-tee").exists()
    assert Product.objects.filter(slug="custom-tee", is_custom_blank=True).exists()

    tshirts = Category.objects.get(slug="t-shirts")
    Product.objects.create(
        name="Real Launch Tee",
        slug="real-launch-tee",
        category=tshirts,
        base_price=Decimal("999.00"),
    )

    call_command("purge_demo", "--noinput")

    assert not Product.objects.filter(slug__in=["classic-black-tee", "custom-tee"]).exists()
    assert Product.objects.filter(slug="real-launch-tee").exists()
    # The reused category still holds the real product, so it survives.
    assert Category.objects.filter(slug="t-shirts").exists()
    # A demo-only collection emptied by the purge is removed.
    assert not Collection.objects.filter(slug="hoodie-collection").exists()


def test_dry_run_deletes_nothing():
    call_command("seed_catalog")
    before = Product.objects.count()

    call_command("purge_demo", "--dry-run")

    assert Product.objects.count() == before
