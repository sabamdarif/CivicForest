"""The suggest endpoint: what it returns, what it refuses, and what it never does.

Two of these matter more than the shape of the payload. The endpoint must not be usable to walk
the catalogue, and it must not write a search log row: an autocomplete fires on keystrokes, so
logging here would drown the report M8 builds from that table.
"""

import pytest
from django.core.cache import cache
from django.core.management import call_command
from rest_framework.throttling import SimpleRateThrottle

from apps.catalog.models import Product
from apps.search import services
from apps.search.models import SearchQueryLog

pytestmark = pytest.mark.django_db

URL = "/api/v1/search/suggest/"


@pytest.fixture(autouse=True)
def documents(catalogue):
    cache.clear()  # the payload is cached for a minute, and tests share a process
    call_command("reindex_search")
    return catalogue


def test_a_match_comes_back_with_everything_a_row_needs(client, documents):
    body = client.get(URL, {"q": "hoodie"}).json()

    assert body["total"] == 1
    hit = body["products"][0]
    assert hit["name"] == "Green Hoodie"
    assert hit["url"] == "/product/green-hoodie/"
    assert set(hit) == {"name", "url", "image", "srcset", "price", "mrp"}


def test_the_price_is_the_one_the_card_prints(client, documents):
    hoodie = documents["hoodie"]
    hit = client.get(URL, {"q": "hoodie"}).json()["products"][0]

    price, _ = services.catalog.price_display(hoodie)
    # The cheapest variant undercuts the product's own base price, so a recomputed number here
    # would read 1,499 rather than 1,299.
    assert hit["price"] == services.rupees(price) == "₹1,299.00"


def test_an_mrp_is_shown_only_when_it_is_a_real_saving(client, documents):
    hits = {hit["name"]: hit for hit in client.get(URL, {"q": "tee"}).json()["products"]}

    assert hits["Graphic Tee"]["mrp"] == "₹1,199.00"
    assert hits["Plain Tee"]["mrp"] == ""


def test_matching_categories_and_popular_queries_ride_along(client, documents):
    SearchQueryLog.objects.create(query="hoodie", result_count=1)
    SearchQueryLog.objects.create(query="hoodie", result_count=1)
    SearchQueryLog.objects.create(query="nothing here", result_count=0)

    body = client.get(URL, {"q": "hoodie"}).json()

    assert body["categories"] == [{"name": "Hoodies", "url": "/shop/hoodies/"}]
    # Only terms that found something: suggesting a dead end helps nobody.
    assert body["queries"] == ["hoodie"]


@pytest.mark.parametrize("term", ["", "h", "   "])
def test_a_query_too_short_to_mean_anything_returns_nothing(client, documents, term):
    body = client.get(URL, {"q": term}).json()

    assert body == {"products": [], "categories": [], "queries": [], "total": 0}


def test_the_payload_is_capped_and_cannot_be_paged(client, documents):
    for index in range(9):
        Product.objects.create(
            name=f"Hoodie {index}",
            slug=f"hoodie-{index}",
            category=documents["hoodie"].category,
            base_price=999,
            hsn_code="61102000",
        )
    call_command("reindex_search", stale=True)

    body = client.get(URL, {"q": "hoodie", "page": 2, "offset": 6, "limit": 100}).json()

    assert len(body["products"]) == services.SUGGEST_PRODUCTS
    # The total is honest about how many there are; the rows are not there to be walked.
    assert body["total"] == 10


def test_an_over_long_query_is_refused_rather_than_tokenised(client, documents):
    assert client.get(URL, {"q": "x" * 500}).status_code == 400


def test_the_endpoint_never_writes_a_log_row(client, documents):
    client.get(URL, {"q": "hoodie"})
    client.get(URL, {"q": "hoodei"})

    assert SearchQueryLog.objects.count() == 0


def test_the_throttle_is_the_search_scope(client, documents, monkeypatch):
    # The rate is a class attribute read at import, so overriding the setting is not enough.
    monkeypatch.setitem(SimpleRateThrottle.THROTTLE_RATES, "search", "2/min")

    codes = [client.get(URL, {"q": f"hoodie{n}"}).status_code for n in range(3)]

    assert codes == [200, 200, 429]


def test_a_repeat_query_is_answered_from_the_cache(client, documents, django_assert_num_queries):
    client.get(URL, {"q": "hoodie"})

    with django_assert_num_queries(0):
        client.get(URL, {"q": "hoodie"})
