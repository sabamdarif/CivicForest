"""Storefront views for the catalogue.

Thin by rule: every one reads the query string, calls a service, and renders. The browse pages
answer twice from the same region template, whole page or just the region JavaScript swaps, so
the no-JS and JS paths can never render different results (D2, P6).
"""

from django.http import Http404
from django.shortcuts import render

from . import services

PARTIAL_HEADER = "X-Partial"

# Every browse page hands its filter form to /shop/, so one canonical URL describes any result
# set and a scoped page is only ever the pretty way in.
BROWSE_ACTION = "/shop/"


def _render(request, whole: str, region: str, context: dict):
    """The swap region on a JavaScript fetch, the whole page otherwise."""
    template = region if request.headers.get(PARTIAL_HEADER) else whole
    response = render(request, template, context)
    response["Vary"] = PARTIAL_HEADER
    return response


def _browse(request, filters: dict, **extra) -> dict:
    """The context `shop/_shop.html` needs, whichever page is wrapping it."""
    results = services.product_list(
        filters, services.parse_sort(request.GET.get("sort")), request.GET.get("page")
    )
    return {
        "results": results,
        "filters": filters,
        "hidden": services.filter_pairs(filters),
        "sort_options": services.sort_options(),
        "action": BROWSE_ACTION,
        **extra,
    }


def shop(request, category: str = ""):
    """The product grid, all filter state in the query string (D2).

    A category in the path is the same thing as ``?category=slug`` with a heading on top, so
    the panel still posts to /shop/ and the URL after a filter change stays canonical.
    """
    filters = services.parse_filters(request.GET)
    scoped = None
    if category:
        scoped = services.active_categories().filter(slug=category).first()
        if not scoped:
            raise Http404
        filters["category"] = [scoped.slug]

    context = _browse(
        request,
        filters,
        category=scoped,
        heading=scoped.name if scoped else "Shop all",
        blurb=scoped.description if scoped else "",
        trail=[("Home", "/"), ("Shop", "/shop/")] if scoped else [("Home", "/")],
        current=scoped.name if scoped else "Shop",
    )
    return _render(request, "shop/list.html", "shop/_shop.html", context)


def collection_index(request):
    """The curated groups (C7), each with its own copy and imagery."""
    return render(
        request,
        "collections/index.html",
        {
            "collections": services.listed_collections(),
            "trail": [("Home", "/")],
            "current": "Collections",
        },
    )


def collection_detail(request, slug: str):
    """One collection, browsed with the same grid, filters and sorts as the shop."""
    collection = services.collection_by_slug(slug)
    if not collection:
        raise Http404

    filters = services.parse_filters(request.GET)
    filters["collection"] = [collection.slug]
    context = _browse(
        request,
        filters,
        collection=collection,
        heading=collection.name,
        blurb=collection.description,
        trail=[("Home", "/"), ("Collections", "/collections/")],
        current=collection.name,
    )
    return _render(request, "collections/detail.html", "shop/_shop.html", context)
