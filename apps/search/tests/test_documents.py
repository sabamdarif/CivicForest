"""The document: what goes in it, what marks it stale, and what rebuilds it.

Nothing here asserts ranking, which is Postgres-only and lives in `test_ranking_postgres.py`.
The blob and the staleness rules are backend-independent, so they run in the offline suite too.
"""

import pytest
from django.core.management import call_command

from apps.catalog.models import Collection, Product, ProductVariant, Tag
from apps.search import services
from apps.search.models import SearchDocument

pytestmark = pytest.mark.django_db


def _document(product) -> SearchDocument:
    return SearchDocument.objects.get(product=product)


def test_the_blob_holds_every_tier_but_the_description(catalogue):
    hoodie = catalogue["hoodie"]
    hoodie.description = "Brushed inside for winter"
    hoodie.save()
    Tag.objects.create(name="Winter").products.add(hoodie)

    services.refresh(hoodie)
    text = _document(hoodie).text.lower()

    assert "green hoodie" in text  # A: the name
    assert "hoodies" in text  # B: its category
    assert "fleece" in text  # C: its material
    assert "black" in text  # C: a colour, which only a variant carries
    assert "winter" in text  # C: a tag
    # D stays in the vector: word similarity against a whole description clears no floor.
    assert "brushed" not in text


def test_the_blob_carries_a_parent_category_and_every_collection(catalogue):
    services.refresh(catalogue["printed"])
    text = _document(catalogue["printed"]).text.lower()
    assert "graphic tees" in text and "t-shirts" in text

    services.refresh(catalogue["plain"])
    text = _document(catalogue["plain"]).text.lower()
    assert "new arrivals" in text and "staples" in text


def test_refreshing_clears_stale_and_records_when_it_ran(catalogue):
    product = catalogue["plain"]
    services.refresh(product)
    first = _document(product)
    assert first.is_stale is False

    product.save()
    marked = _document(product)
    assert marked.is_stale is True
    # Marking must not look like a rebuild, or a sweep cannot tell what it has done.
    assert marked.updated_at == first.updated_at


@pytest.mark.parametrize("model_name", ["variant", "category", "collection", "tag"])
def test_every_catalogue_edit_marks_its_products_stale(catalogue, model_name):
    plain = catalogue["plain"]
    tag = Tag.objects.create(name="Everyday")
    tag.products.add(plain)
    call_command("reindex_search")
    assert _document(plain).is_stale is False

    match model_name:
        case "variant":
            ProductVariant.objects.filter(product=plain).first().save()
        case "category":
            plain.category.save()
        case "collection":
            Collection.objects.get(slug="staples").save()
        case "tag":
            tag.save()

    assert _document(plain).is_stale is True


def test_deleting_a_variant_or_a_collection_marks_the_product_stale(catalogue):
    plain = catalogue["plain"]
    call_command("reindex_search")

    ProductVariant.objects.filter(product=plain, size="L").delete()
    assert _document(plain).is_stale is True

    call_command("reindex_search", stale=True)
    # A collection's products can only be found before its rows go, hence pre_delete.
    Collection.objects.get(slug="staples").delete()
    assert _document(plain).is_stale is True


def test_a_renamed_parent_category_marks_its_childrens_products_stale(catalogue):
    printed = catalogue["printed"]
    call_command("reindex_search")

    parent = printed.category.parent
    parent.name = "Tops"
    parent.save()

    assert _document(printed).is_stale is True


def test_the_document_goes_with_the_product(catalogue):
    plain = catalogue["plain"]
    services.refresh(plain)
    ProductVariant.objects.filter(product=plain).delete()
    plain.delete()

    assert not SearchDocument.objects.filter(product_id=plain.pk).exists()


def test_reindex_only_touches_live_products_and_respects_stale_and_batch(catalogue):
    call_command("reindex_search")
    # The retired product is not searchable, so it is not indexed either.
    assert SearchDocument.objects.count() == 3
    assert not SearchDocument.objects.filter(is_stale=True).exists()

    catalogue["plain"].save()
    catalogue["hoodie"].save()
    call_command("reindex_search", stale=True, batch=1)

    assert SearchDocument.objects.filter(is_stale=True).count() == 1


def test_reindex_is_idempotent(catalogue):
    call_command("reindex_search")
    before = _document(catalogue["plain"]).text
    call_command("reindex_search")

    assert _document(catalogue["plain"]).text == before
    assert SearchDocument.objects.count() == Product.objects.filter(is_active=True).count()
