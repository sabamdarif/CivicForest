"""The home page.

The view composes: which bands appear and in what order is content (`HomeSection`), and what
goes inside them is catalogue. Neither service calls the other.
"""

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
