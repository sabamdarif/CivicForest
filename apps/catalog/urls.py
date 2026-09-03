"""Storefront catalogue routes, mounted at the root.

Paths are the ones `rebuild/03-architecture.md` §4 fixes and the header and footer already
link to, so mounting them here is what makes those links live.
"""

from django.urls import path

from . import views

urlpatterns = [
    path("shop/", views.shop, name="shop"),
    path("shop/<slug:category>/", views.shop, name="shop-category"),
    path("collections/", views.collection_index, name="collections"),
    path("collections/<slug:slug>/", views.collection_detail, name="collection-detail"),
]
