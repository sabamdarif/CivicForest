"""Storefront content routes, mounted at the root from ``config/urls.py``.

The static pages are listed explicitly rather than served through a catch-all ``<slug>/``: a
catch-all would shadow every other single-segment route and turn a typo into a page lookup. The
paths match the footer's literal links (rebuild/03-architecture.md §4). Contact and grievance are
their own views (M9.7, M9.6); track order lives in ``apps.orders``.
"""

from django.urls import path

from . import views

# Path segment == page slug for each static page.
_PAGES = [
    "about",
    "sustainability",
    "shipping-delivery",
    "returns-exchanges",
    "size-guide",
    "privacy",
    "terms",
]

# The slugs that actually have a route, so the sitemap never lists a page it cannot serve.
MOUNTED_PAGE_SLUGS = tuple(_PAGES)

urlpatterns = [
    path("faq/", views.faq, name="faq"),
    path("contact/", views.contact, name="contact"),
    path("grievance-redressal/", views.grievance, name="grievance"),
]
urlpatterns += [
    path(f"{slug}/", views.page, {"slug": slug}, name=f"page-{slug}") for slug in _PAGES
]
