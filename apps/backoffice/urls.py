"""Back-office URL map, mounted under `settings.BACKOFFICE_URL` from `config/urls.py`.

Namespaced `backoffice` so templates and tests reverse by name and never hard-code the
env-driven prefix. `/styleguide/` stays at the site root (mounted in `config/urls.py`), not here.
"""

from django.urls import path

from . import views

app_name = "backoffice"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
]
