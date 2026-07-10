"""Search endpoints.

- ``/api/v1/search/suggest`` — autocomplete dropdown. Minimal payload, tight throttle,
  short-lived Redis cache for popular anonymous prefixes (plan.md §7).
- ``/api/v1/search`` — full results page. Same service, larger page, logs analytics.
"""

from __future__ import annotations

from django.core.cache import cache
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from . import services
from .models import SearchQueryLog
from .serializers import SuggestionHitSerializer

SUGGEST_LIMIT = 8
SUGGEST_CACHE_TTL = 30  # seconds — most autocomplete traffic clusters on few prefixes
MIN_QUERY_LEN = 2


class SuggestThrottle(ScopedRateThrottle):
    scope = "search"


@api_view(["GET"])
@permission_classes([AllowAny])
@throttle_classes([SuggestThrottle])
def suggest(request):
    query = request.query_params.get("q", "").strip()
    if len(query) < MIN_QUERY_LEN:
        return Response({"query": query, "hits": []})

    cache_key = f"suggest:{query.lower()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return Response(cached)

    result = services.search_products(query, limit=SUGGEST_LIMIT)
    payload = {
        "query": query,
        "hits": SuggestionHitSerializer(result["hits"], many=True).data,
    }
    cache.set(cache_key, payload, SUGGEST_CACHE_TTL)
    return Response(payload)


@api_view(["GET"])
@permission_classes([AllowAny])
def search(request):
    query = request.query_params.get("q", "").strip()
    try:
        page = max(1, int(request.query_params.get("page", 1)))
    except ValueError:
        page = 1
    page_size = min(48, max(1, int(request.query_params.get("page_size", 12) or 12)))
    offset = (page - 1) * page_size

    if len(query) < MIN_QUERY_LEN:
        return Response(
            {"query": query, "results": [], "count": 0, "page": page, "page_size": page_size}
        )

    result = services.search_products(query, limit=page_size, offset=offset)

    # Fire-and-forget analytics; never let logging failure break the response.
    try:
        SearchQueryLog.objects.create(
            query=query,
            result_count=result["total"],
            engine=result["engine"],
            session_key=request.session.session_key or "",
        )
    except Exception:  # noqa: BLE001
        pass

    return Response(
        {
            "query": query,
            "results": SuggestionHitSerializer(result["hits"], many=True).data,
            "count": result["total"],
            "page": page,
            "page_size": page_size,
            "engine": result["engine"],
        }
    )
