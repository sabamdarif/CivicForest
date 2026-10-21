"""Custom-print JSON routes, mounted under /api/v1/.

The design tool posts here: mint an upload URL, then confirm the upload to trigger sanitise.
``dev-upload`` is the local stand-in for R2 and is inert once a real bucket is configured.
"""

from django.urls import path

from . import views

urlpatterns = [
    path("designs/upload-url/", views.DesignUploadUrlView.as_view(), name="design-upload-url"),
    path("designs/add-to-cart/", views.AddToCartView.as_view(), name="design-add-to-cart"),
    path("designs/dev-upload/", views.dev_upload, name="designs-dev-upload"),
    path("designs/<uuid:pk>/complete/", views.DesignCompleteView.as_view(), name="design-complete"),
]
