"""Search's internal JSON route, mounted under /api/v1/ (A13).

The storefront route is in `urls.py`, the same split `apps/catalog` and `apps/cart` use.
"""

from django.urls import path

from .views import SuggestView

urlpatterns = [
    path("search/suggest/", SuggestView.as_view(), name="search-suggest"),
]
