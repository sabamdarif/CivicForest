"""Root URL configuration.

The admin lives at a non-guessable, env-driven path, never /admin/. Everything else is
mounted under a stable prefix: ``/api/v1/`` for this site's own JSON endpoints.
"""

import secrets

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.sitemaps.views import sitemap
from django.http import JsonResponse
from django.urls import include, path

from apps.common.sitemaps import SITEMAPS
from apps.common.views import styleguide
from apps.content.views import home


def healthz(request):
    """Liveness for an external monitor, plus dependency detail for whoever holds the
    token. The bare 200 leaks nothing, so it needs no secret to poll."""
    if not _health_authorized(request):
        return JsonResponse({"status": "ok"})

    from django.core.cache import cache
    from django.db import connection

    checks = {}
    try:
        connection.cursor().execute("SELECT 1")
        checks["database"] = "ok"
    except Exception:  # noqa: BLE001
        checks["database"] = "error"
    try:
        cache.set("healthz", "1", 5)
        checks["cache"] = "ok" if cache.get("healthz") == "1" else "error"
    except Exception:  # noqa: BLE001
        checks["cache"] = "error"

    ok = all(v == "ok" for v in checks.values())
    return JsonResponse(
        {"status": "ok" if ok else "degraded", "checks": checks}, status=200 if ok else 503
    )


def _health_authorized(request) -> bool:
    expected = settings.HEALTH_CHECK_TOKEN
    supplied = request.headers.get("X-Health-Token", "")
    return bool(expected) and secrets.compare_digest(supplied, expected)


urlpatterns = [
    path("", home, name="home"),
    path("", include("apps.catalog.urls")),
    path("", include("apps.cart.urls")),
    path("", include("apps.search.urls")),
    path("healthz/", healthz, name="healthz"),
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="sitemap"),
    # Staff-only, and the regression surface for every stylesheet.
    path("styleguide/", styleguide, name="styleguide"),
    path(settings.ADMIN_URL, admin.site.urls),
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.cart.api_urls")),
    path("api/v1/", include("apps.orders.urls")),
    path("api/v1/", include("apps.payments.urls")),
    path("api/v1/", include("apps.custom_orders.urls")),
    path("api/v1/", include("apps.search.api_urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
