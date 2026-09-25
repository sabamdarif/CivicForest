"""Back-office URL map, mounted under `settings.BACKOFFICE_URL` from `config/urls.py`.

Namespaced `backoffice` so templates and tests reverse by name and never hard-code the
env-driven prefix. `/styleguide/` stays at the site root (mounted in `config/urls.py`), not here.
"""

from django.urls import path

from . import views

app_name = "backoffice"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("orders/", views.OrderQueueView.as_view(), name="orders"),
    path("orders/bulk/", views.OrderBulkActionView.as_view(), name="order_bulk"),
    path("orders/<str:order_number>/", views.OrderDetailView.as_view(), name="order_detail"),
    path(
        "orders/<str:order_number>/slip/",
        views.OrderPackingSlipView.as_view(),
        name="order_packing_slip",
    ),
    path(
        "orders/<str:order_number>/action/",
        views.OrderActionView.as_view(),
        name="order_action",
    ),
    path("designs/", views.DesignReviewQueueView.as_view(), name="designs"),
    path("designs/<uuid:pk>/", views.DesignReviewDetailView.as_view(), name="design_detail"),
    path(
        "designs/<uuid:pk>/action/",
        views.DesignReviewActionView.as_view(),
        name="design_action",
    ),
    path("products/", views.ProductListView.as_view(), name="products"),
    path("products/bulk/", views.ProductBulkUpdateView.as_view(), name="product_bulk"),
    path("products/import/", views.ProductImportView.as_view(), name="product_import"),
    path("products/new/", views.ProductCreateView.as_view(), name="product_new"),
    path("products/<uuid:pk>/", views.ProductEditView.as_view(), name="product_edit"),
    path("products/<uuid:pk>/action/", views.ProductActionView.as_view(), name="product_action"),
]
