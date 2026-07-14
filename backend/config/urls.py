"""Root URL configuration.

The admin lives at a non-guessable, env-driven path (never /admin/ — plan.md §11).
The versioned API and allauth's headless endpoints are mounted under stable prefixes
that Caddy forwards to Django.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import JsonResponse
from django.urls import include, path


def healthz(_request):
    """Liveness probe — excluded from auth and throttling."""
    return JsonResponse({"status": "ok"})


def readyz(_request):
    """Readiness probe — checks the backing services this process needs (plan.md §16).

    Returns 503 if the database or cache is unreachable so an orchestrator/load
    balancer routes traffic away until dependencies recover."""
    from django.core.cache import cache
    from django.db import connection

    checks = {}
    try:
        connection.cursor().execute("SELECT 1")
        checks["database"] = "ok"
    except Exception:  # noqa: BLE001
        checks["database"] = "error"
    try:
        cache.set("readyz", "1", 5)
        checks["cache"] = "ok" if cache.get("readyz") == "1" else "error"
    except Exception:  # noqa: BLE001
        checks["cache"] = "error"

    ok = all(v == "ok" for v in checks.values())
    return JsonResponse(
        {"status": "ok" if ok else "degraded", "checks": checks}, status=200 if ok else 503
    )


urlpatterns = [
    path("healthz", healthz),
    path("readyz", readyz),
    path(settings.ADMIN_URL, admin.site.urls),
    # allauth headless (browser/session flavor) powers the Next.js auth UI.
    path("_allauth/", include("allauth.headless.urls")),
    path("api/v1/", include("apps.catalog.urls")),
    path("api/v1/", include("apps.search.urls")),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.cart.urls")),
    path("api/v1/", include("apps.orders.urls")),
    path("api/v1/", include("apps.payments.urls")),
    path("api/v1/", include("apps.custom_orders.urls")),
]

if settings.DEBUG:
    from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

    urlpatterns += [
        path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
        path(
            "api/docs/",
            SpectacularSwaggerView.as_view(url_name="schema"),
            name="swagger-ui",
        ),
    ]
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
