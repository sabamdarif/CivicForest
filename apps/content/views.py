"""The home page and the static content surface (M9.5).

The home view composes: which bands appear and in what order is content (`HomeSection`), and what
goes inside them is catalogue. Neither service calls the other. `page` renders a published `Page`
by slug (a draft or missing slug is a 404); `faq` renders the active FAQ entries as an accordion.
"""

from django.http import Http404
from django.shortcuts import render

from apps.catalog import services as catalog
from apps.common import seo

from . import services


def home(request):
    return render(
        request,
        "home.html",
        {
            "sections": services.home_sections(),
            # Four tiles, as the reference shows. Which four is display_order's job, and the
            # full set is on /shop/ behind the category facet.
            "categories": catalog.nav_categories()[:4],
            "just_landed": catalog.new_arrivals(4),
            "structured_data": [seo.organisation(request), seo.website(request)],
        },
    )


def page(request, slug):
    """A published static page (L2). A draft or unknown slug is a 404, never a blank shell."""
    content_page = services.get_published_page(slug)
    if content_page is None:
        raise Http404
    trail = [("Home", "/")]
    return render(
        request,
        "content/page.html",
        {
            "page": content_page,
            "trail": trail,
            "current": content_page.title,
            "structured_data": [seo.breadcrumb_list(request, trail, content_page.title)],
        },
    )


def faq(request):
    """The FAQ accordion with FAQPage markup (N3), grouped by category."""
    groups = services.faq_grouped()
    return render(
        request,
        "content/faq.html",
        {"faq_groups": groups, "structured_data": [seo.faq_page(request, groups)]},
    )
