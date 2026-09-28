"""Storefront content routes, mounted at the root from ``config/urls.py``.

The static pages are listed explicitly rather than served through a catch-all ``<slug>/``: a
catch-all would shadow every other single-segment route and turn a typo into a page lookup. The
paths match the footer's literal links (rebuild/03-architecture.md §4). Contact, grievance and the
newsletter opt-in routes are their own views (M9.7, M9.6, M9.8); track order is in ``apps.orders``.
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
    path("newsletter/subscribe/", views.newsletter_subscribe, name="newsletter_subscribe"),
    path("newsletter/confirm/<str:token>/", views.newsletter_confirm, name="newsletter_confirm"),
    path(
        "newsletter/unsubscribe/<str:token>/",
        views.newsletter_unsubscribe,
        name="newsletter_unsubscribe",
    ),
]
urlpatterns += [
    path(f"{slug}/", views.page, {"slug": slug}, name=f"page-{slug}") for slug in _PAGES
]
