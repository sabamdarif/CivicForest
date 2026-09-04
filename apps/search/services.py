"""Search services: building the document, and turning a typed query into a result set.

The document is denormalised on purpose: one row per product, so a query never joins across the
catalogue mid-request. ``text`` is deliberately short, because it is what trigram matching reads
and ``word_similarity()`` against a whole description would never clear a floor.

The query path is one public function, ``ranking()``, which hands the catalogue a restriction and
an order rather than a queryset. That keeps one listing implementation in `apps/catalog` and the
only vendor branch here: Postgres gets the weighted vector and the trigram fallback, SQLite gets
substring matching so a local development server still answers /search/ (A10).

Money never appears here except through ``catalog.services.card_data``, which is the one place a
product is mapped for display.
"""

import re

from django.contrib.postgres.search import (
    SearchQuery,
    SearchRank,
    SearchVector,
    TrigramSimilarity,
    TrigramWordSimilarity,
)
from django.core.cache import cache
from django.db import connection
from django.db.models import Count, F, Q, Value
from django.utils import timezone

from apps.catalog import services as catalog
from apps.catalog.models import Material, Tag
from apps.common.formatting import rupees

from .models import MAX_QUERY_LENGTH, SearchDocument, SearchQueryLog, SearchSynonym

CONFIG = "english"  # the stored vector and every query must agree on the dictionary
TOKEN = re.compile(r"[a-z0-9]+")
MAX_TOKENS = 8
SIMILARITY_FLOOR = 0.3  # M3 task 4
MIN_QUERY_LENGTH = 2  # one letter matches most of the catalogue and helps nobody

# The suggest payload is capped rather than paginated, so there is no offset to walk.
SUGGEST_TTL = 60
SUGGEST_PRODUCTS = 6
SUGGEST_CATEGORIES = 4
SUGGEST_QUERIES = 5


# ── The document (M3.2) ──────────────────────────────────────────────────────
def _parts(product) -> tuple[str, str, str, str]:
    """The four weighted tiers: name A, taxonomy B, tags, material and colours C, body D.

    Colours are in C beyond what task 2 lists, because "black hoodie" is an ordinary query and
    a colour exists only on a variant. Sizes stay out: M and L as search tokens are noise.
    """
    category = product.category
    taxonomy = [category.name] if category else []
    if category and category.parent:
        taxonomy.append(category.parent.name)
    taxonomy += [collection.name for collection in product.collections.all()]

    facets = [tag.name for tag in product.tags.all()]
    if product.material:
        facets.append(product.material.name)
    facets += sorted({variant.color for variant in product.variants.all() if variant.color})

    return product.name, " ".join(taxonomy), " ".join(facets), product.description


def _weighted(text: str, weight: str) -> SearchVector:
    return SearchVector(Value(text), weight=weight, config=CONFIG)


def refresh(product) -> None:
    """Rebuild one product's document.

    Called from the admin save path and from ``reindex_search``, never from a customer request
    (M3 task 3). The vector is an expression, so it is written with an UPDATE: an INSERT cannot
    carry one.
    """
    name, taxonomy, facets, body = _parts(product)
    fields = {
        # Short on purpose: word_similarity() against a whole description would never clear
        # the floor, and this column is what typo tolerance and the SQLite path both read.
        "text": " ".join(part for part in (name, taxonomy, facets) if part),
        "is_stale": False,
        "updated_at": timezone.now(),
    }
    if connection.vendor == "postgresql":
        fields["vector"] = (
            _weighted(name, "A")
            + _weighted(taxonomy, "B")
            + _weighted(facets, "C")
            + _weighted(body, "D")
        )
    document, _ = SearchDocument.objects.get_or_create(product=product)
    SearchDocument.objects.filter(pk=document.pk).update(**fields)


def indexable():
    """Products a document is built from, with everything ``_parts`` reads prefetched."""
    return catalog.active_products().prefetch_related("collections")


# ── Synonyms (decision 6) ────────────────────────────────────────────────────
def _groups() -> list[set[str]]:
    """Every active equivalence group, lowercased.

    Symmetric, so one row covers every direction: a query matching the term or any member of
    the expansion searches for all of them.
    """
    rows = SearchSynonym.objects.filter(is_active=True).values_list("term", "expansion")
    groups = []
    for term, expansion in rows:
        members = {part.strip().lower() for part in expansion.split(",") if part.strip()}
        groups.append(members | {term.strip().lower()})
    return groups


def clean(raw: str | None) -> str:
    """The query as it is echoed, logged and searched: trimmed, collapsed, capped."""
    return " ".join((raw or "").split())[:MAX_QUERY_LENGTH]


def _expansions(term: str) -> list[list[str]]:
    """Alternatives per query part, expanded through the synonym table.

    The whole term is looked up first, so a hyphenated spelling like "t-shirt" still finds its
    group even though it tokenises into two words.
    """
    groups = _groups()
    whole = term.lower()
    for group in groups:
        if whole in group:
            return [sorted(group)]

    parts = []
    for token in TOKEN.findall(whole)[:MAX_TOKENS]:
        alternatives = {token}
        for group in groups:
            if token in group:
                alternatives |= group
        parts.append(sorted(alternatives))
    return parts


# ── The query path (M3.4) ────────────────────────────────────────────────────
def _tsquery(parts: list[list[str]]) -> str:
    """Alternatives ORed, parts ANDed, every alternative a prefix match.

    Raw rather than websearch, because prefix matching is what lets a half-typed word find
    anything. Safe: every token is alnum-only, so the string cannot be malformed or injected.
    """
    clauses = []
    for alternatives in parts:
        phrases = [" <-> ".join(TOKEN.findall(alternative)) for alternative in alternatives]
        clauses.append(" | ".join(f"{phrase}:*" for phrase in phrases if phrase))
    return " & ".join(f"({clause})" for clause in clauses if clause)


def _substring_ranking(parts: list[list[str]]) -> catalog.Ranking:
    """SQLite only: the same alternatives as substrings of the same blob.

    No rank and no typo tolerance, so relevance keeps its no-query meaning. This exists to keep
    a local development server working (A10); CI and production run the Postgres path.
    """
    where = Q()
    for alternatives in parts:
        clause = Q()
        for alternative in alternatives:
            clause |= Q(search_document__text__icontains=alternative)
        where &= clause
    return catalog.Ranking(where=where, aliases={}, order_by=())


def ranking(term: str) -> catalog.Ranking | None:
    """What restricts and orders a search, or None when there is nothing to search for."""
    term = clean(term)
    parts = _expansions(term)
    if not any(parts):
        return None
    if connection.vendor != "postgresql":
        return _substring_ranking(parts)

    query = SearchQuery(_tsquery(parts), search_type="raw", config=CONFIG)
    return catalog.Ranking(
        # Word similarity, not plain similarity: the latter compares whole strings and cannot
        # find one misspelt word inside a multi-word document, which is the entire point.
        where=Q(search_document__vector=query) | Q(word_sim__gte=SIMILARITY_FLOOR),
        aliases={
            "rank": SearchRank(F("search_document__vector"), query),
            "word_sim": TrigramWordSimilarity(term, "search_document__text"),
        },
        order_by=("-rank", "-word_sim"),
    )


def did_you_mean(term: str) -> str:
    """The closest catalogue word to a query that found nothing, or "".

    Real trigram output or nothing at all: J9 forbids inventing a suggestion. The vocabularies
    are the source because they are curated and short, where a product name is a sentence.
    """
    term = clean(term)
    if not term or connection.vendor != "postgresql":
        return ""

    best, score = "", 0.0
    for queryset in (catalog.active_categories(), Tag.objects.all(), Material.objects.all()):
        row = (
            queryset.annotate(sim=TrigramSimilarity("name", term))
            .filter(sim__gte=SIMILARITY_FLOOR)
            .order_by("-sim")
            .values_list("name", "sim")
            .first()
        )
        if row and row[1] > score and row[0].lower() != term.lower():
            best, score = row
    return best


# ── Suggest (M3.5) ───────────────────────────────────────────────────────────
def matching(term: str, limit: int) -> tuple[list, int]:
    """The best few products for a term and how many there are in total.

    A lean version of the results page: no facets, no filters, no pagination, which is what
    keeps the autocomplete to two queries.
    """
    rank = ranking(term)
    if rank is None:
        return [], 0
    found = catalog.ranked(catalog.active_products(), rank).order_by(
        *catalog.order_for(catalog.DEFAULT_SORT, rank)
    )
    return list(found[:limit]), found.count()


def popular_queries(limit: int = SUGGEST_QUERIES) -> list[str]:
    """The most-searched terms that found something (D7).

    ``order_by()`` first, or the model's own ordering joins the GROUP BY and every row becomes
    its own group.
    """
    rows = (
        SearchQueryLog.objects.filter(result_count__gt=0)
        .order_by()
        .values("query")
        .annotate(total=Count("id"))
        .order_by("-total", "query")[:limit]
    )
    return [row["query"] for row in rows]


def _suggestion_card(product) -> dict:
    """One suggestion row, read off the one mapping a product card already uses, so a price
    here can never disagree with the price on a card."""
    data = catalog.card_data(product)
    return {
        "name": data["name"],
        "url": data["href"],
        "image": data["image"],
        "srcset": data["srcset"],
        "price": rupees(data["amount"]),
        "mrp": rupees(data["mrp"]) if data["mrp"] else "",
    }


def suggest(term: str) -> dict:
    """The autocomplete payload (D7), capped and cached for a minute.

    The cache is a latency saving only, and is per function instance until A2's database cache
    table exists, so nothing about the cap may depend on it being warm.
    """
    term = clean(term)
    if len(term) < MIN_QUERY_LENGTH:
        return {"products": [], "categories": [], "queries": [], "total": 0}

    key = "search:suggest:" + "-".join(TOKEN.findall(term.lower())[:MAX_TOKENS])
    payload = cache.get(key)
    if payload is None:
        products, total = matching(term, SUGGEST_PRODUCTS)
        categories = catalog.active_categories().filter(name__icontains=term)[:SUGGEST_CATEGORIES]
        payload = {
            "products": [_suggestion_card(product) for product in products],
            "categories": [
                {"name": category.name, "url": category.get_absolute_url()}
                for category in categories
            ],
            "queries": popular_queries(),
            "total": total,
        }
        cache.set(key, payload, SUGGEST_TTL)
    return payload


def popular_products(limit: int = 4) -> list:
    """What to offer when there is nothing to show (D8): what sells, or what is newest.

    Never empty on a stocked catalogue, which is what makes a zero-result page a way forward
    rather than a dead end.
    """
    return list(catalog.bestsellers(limit)) or list(catalog.new_arrivals(limit))


def log_query(request, term: str, result_count: int) -> None:
    """One row per submitted query (D9).

    The caller decides when: only a full first-page render, so paging through results and a
    JavaScript filter swap cannot inflate a term's count, and the suggest endpoint never logs.
    M8 reads the zero-result rows (O1, O13) and ``popular_queries`` reads the rest.
    """
    SearchQueryLog.objects.create(
        query=term,
        result_count=result_count,
        session_key=request.session.session_key or "",
    )
