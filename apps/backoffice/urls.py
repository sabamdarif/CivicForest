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
    path("inventory/", views.InventoryView.as_view(), name="inventory"),
    path("inventory/<uuid:pk>/adjust/", views.StockAdjustView.as_view(), name="inventory_adjust"),
    path("coupons/", views.CouponListView.as_view(), name="coupons"),
    path("coupons/new/", views.CouponCreateView.as_view(), name="coupon_new"),
    path("coupons/<uuid:pk>/", views.CouponEditView.as_view(), name="coupon_edit"),
    path("coupons/<uuid:pk>/report/", views.CouponReportView.as_view(), name="coupon_report"),
    path("coupons/<uuid:pk>/action/", views.CouponActionView.as_view(), name="coupon_action"),
    path("customers/", views.CustomerListView.as_view(), name="customers"),
    path("customers/<uuid:pk>/", views.CustomerDetailView.as_view(), name="customer_detail"),
    path("customers/<uuid:pk>/action/", views.CustomerBlockView.as_view(), name="customer_action"),
    path("content/", views.ContentView.as_view(), name="content"),
    path("content/bar/new/", views.AnnouncementCreateView.as_view(), name="announcement_new"),
    path("content/bar/<uuid:pk>/", views.AnnouncementEditView.as_view(), name="announcement_edit"),
    path("content/section/new/", views.HomeSectionCreateView.as_view(), name="home_section_new"),
    path(
        "content/section/<uuid:pk>/", views.HomeSectionEditView.as_view(), name="home_section_edit"
    ),
    path("content/category/<uuid:pk>/", views.CategoryEditView.as_view(), name="category_edit"),
    path(
        "content/collection/<uuid:pk>/", views.CollectionEditView.as_view(), name="collection_edit"
    ),
    path("jobs/", views.JobsPanelView.as_view(), name="jobs"),
    path("jobs/run/", views.JobRunNowView.as_view(), name="job_run"),
    path("jobs/email/<uuid:pk>/resend/", views.EmailResendView.as_view(), name="email_resend"),
    path("reports/", views.ReportsView.as_view(), name="reports"),
    path("audit/", views.AuditLogView.as_view(), name="audit"),
]
