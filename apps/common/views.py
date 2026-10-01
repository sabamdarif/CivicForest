"""Site-wide error pages (M9.12).

``handler404`` and ``handler500`` are wired to these from ``config/urls.py``. The 500 page is
deliberately rendered without touching the database or the shell layout, because the thing that
raised the 500 may be the database itself; a branded but self-contained page always renders.
"""

from django.shortcuts import render


def not_found(request, exception=None):
    """Branded 404. The shell is fine to render here: the database is up, the URL simply missed."""
    return render(request, "errors/404.html", status=404)


def server_error(request):
    """Branded 500, standalone and database-free so it renders even when the shell cannot."""
    return render(request, "errors/500.html", status=500)
