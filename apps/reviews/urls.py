"""Reviews storefront routes, mounted at the root from ``config/urls.py``."""

from django.urls import path

from . import views

urlpatterns = [
    path("account/reviews/new/<uuid:item_id>/", views.write_review, name="review-write"),
]
