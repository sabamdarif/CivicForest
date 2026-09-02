"""Content lookups the templates call. One indexed query per page render, no cache: the
production cache is the database too, so a cached read would cost the same query."""

from .models import AnnouncementBar


def current_announcement() -> AnnouncementBar | None:
    """The bar to render, or None when it is switched off or its window has passed."""
    return AnnouncementBar.objects.live().first()
