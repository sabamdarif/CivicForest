"""Custom-line storefront routes, mounted at the root (M7.4, M7.5).

The JSON routes the tool posts to live in ``urls.py`` under /api/v1/; these are the two pages
a customer sees."""

from django.urls import path

from . import storefront_views

urlpatterns = [
    path("customise/", storefront_views.customise_landing, name="customise-landing"),
    path("account/designs/", storefront_views.account_designs, name="account-designs"),
    path("customise/<slug:slug>/", storefront_views.customise_designer, name="customise-designer"),
]
