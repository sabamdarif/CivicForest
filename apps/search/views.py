"""Search views: the internal JSON suggest endpoint.

The storefront's own `/search/` page is in the same app; this module holds the API surface A13
describes: session plus CSRF, same origin, not publicly documented.
"""

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from . import services
from .serializers import SuggestQuerySerializer


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
