"""The search results page, mounted at the root.

`/search/` is the path `rebuild/03-architecture.md` §4 fixes, the header's search icon already
links to, and `seo.website()` advertises in the WebSite JSON-LD.
"""

from django.urls import path

from . import views

urlpatterns = [
    path("search/", views.results, name="search"),
]
