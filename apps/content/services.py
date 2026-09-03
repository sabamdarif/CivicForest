"""Content lookups the templates call. One indexed query per page render, no cache: the
production cache is the database too, so a cached read would cost the same query."""

from .models import AnnouncementBar, HomeSection


def current_announcement() -> AnnouncementBar | None:
    """The bar to render, or None when it is switched off or its window has passed."""
    return AnnouncementBar.objects.live().first()


def home_sections() -> list[HomeSection]:
    """The bands the home page renders, in the order staff put them in."""
    return list(HomeSection.objects.filter(is_active=True))
