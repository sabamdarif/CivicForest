from django.urls import path

from .views import search, suggest

urlpatterns = [
    path("search/suggest", suggest, name="search-suggest"),
    path("search", search, name="search"),
]
