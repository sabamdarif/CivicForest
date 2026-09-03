"""Storefront views for the catalogue.

Thin by rule: every one reads the query string, calls a service, and renders. The shop view
answers twice from the same template, whole page or just the region JavaScript swaps, so the
no-JS and JS paths can never render different results (D2, P6).
"""

from django.http import Http404
from django.shortcuts import render

from . import services

PARTIAL_HEADER = "X-Partial"


def _partial(request, whole: str, region: str) -> str:
    """The region on a JavaScript fetch, the whole page otherwise."""
    return region if request.headers.get(PARTIAL_HEADER) else whole


def shop(request, category: str = ""):
    """The product grid, all filter state in the query string (D2).

    A category in the path is the same thing as ``?category=slug`` with a heading on top, so
    the filter form always posts to /shop/ and one canonical URL describes any result set.
    """
    filters = services.parse_filters(request.GET)
    scoped = None
    if category:
        scoped = services.active_categories().filter(slug=category).first()
        if not scoped:
            raise Http404
        filters["category"] = [scoped.slug]

    results = services.product_list(
        filters, services.parse_sort(request.GET.get("sort")), request.GET.get("page")
    )
    context = {
        "results": results,
        "filters": filters,
        "hidden": services.filter_pairs(filters),
        "sort_options": services.sort_options(),
        "action": "/shop/",
        "category": scoped,
        "heading": scoped.name if scoped else "Shop all",
        "blurb": scoped.description if scoped else "",
        "trail": [("Home", "/"), ("Shop", "/shop/")] if scoped else [("Home", "/")],
        "current": scoped.name if scoped else "Shop",
    }
    response = render(request, _partial(request, "shop/list.html", "shop/_shop.html"), context)
    response["Vary"] = PARTIAL_HEADER
    return response
