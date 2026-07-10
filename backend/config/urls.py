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


urlpatterns = [
    path("healthz", healthz),
    path(settings.ADMIN_URL, admin.site.urls),
    # allauth headless (browser/session flavor) powers the Next.js auth UI.
    path("_allauth/", include("allauth.headless.urls")),
    path("api/v1/", include("apps.catalog.urls")),
    path("api/v1/", include("apps.search.urls")),
    path("api/v1/", include("apps.accounts.urls")),
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
