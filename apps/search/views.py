"""Search views: the results page and the internal JSON suggest endpoint.

The results page is the shop's own browse region with a query on top, rendered through
`apps/catalog`'s ``browse_context`` and ``render_region``, so filters, facet counts, sorts and
pagination behave identically to /shop/ with or without JavaScript (D2, P6).
"""

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.catalog import services as catalog
from apps.catalog.views import PARTIAL_HEADER, browse_context, render_region

from . import services
from .models import MAX_QUERY_LENGTH
from .serializers import SuggestQuerySerializer

ACTION = "/search/"


def _is_new_search(request, term: str) -> bool:
    """One log row per search (D9): not a paged re-visit, not a JavaScript filter swap."""
    return bool(term) and "page" not in request.GET and not request.headers.get(PARTIAL_HEADER)


def results(request):
    """The results page (M3.6).

    An empty query is not an error and not a redirect to /shop/: the header's search icon links
    straight here, so the page has to stand on its own with a prompt and a way forward.
    """
    term = services.clean(request.GET.get("q"))
    filters = catalog.parse_filters(request.GET)
    filters["q"] = term
    filters["ranking"] = services.ranking(term)

    context = browse_context(
        request,
        filters,
        action=ACTION,
        max_query=MAX_QUERY_LENGTH,
        trail=[("Home", "/")],
        current="Search",
    )
    if _is_new_search(request, term):
        services.log_query(request, term, context["results"].page.paginator.count)
    return render_region(request, "search/results.html", "shop/_shop.html", context)


class SuggestView(APIView):
    """Autocomplete for the header overlay (D7).

    Read-only and open to guests, because browsing needs no account (decision 14). Throttled on
    the `search` scope and capped by the service, so it cannot be walked to enumerate the
    catalogue: there is no offset and no page.
    """

    permission_classes = [AllowAny]
    throttle_scope = "search"

    def get(self, request):
        query = SuggestQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        return Response(services.suggest(query.validated_data.get("q", "")))
