"""Storefront account routes, separate from the versioned JSON API."""

from django.urls import path

from . import views

urlpatterns = [
    path("account/", views.dashboard, name="account-dashboard"),
    path("account/profile/", views.profile, name="account-profile"),
    path("account/addresses/", views.addresses, name="account-addresses"),
    path("account/addresses/add/", views.address_add, name="account-address-add"),
    path("account/addresses/<uuid:pk>/edit/", views.address_edit, name="account-address-edit"),
    path(
        "account/addresses/<uuid:pk>/delete/",
        views.address_delete,
        name="account-address-delete",
    ),
    path(
        "account/addresses/<uuid:pk>/default/",
        views.address_default,
        name="account-address-default",
    ),
    path("account/security/", views.security, name="account-security"),
    path("account/data/", views.data, name="account-data"),
    path("account/data/export/", views.data_export, name="account-data-export"),
    path("account/data/erasure/", views.data_erasure, name="account-data-erasure"),
]
