"""The announcement bar only renders when staff mean it to.

The window is the part worth pinning: an off switch that does not switch off, or a bar that
outlives its end date, is a promise the store did not make.
"""

from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.utils import timezone

from apps.content.models import AnnouncementBar
from apps.content.services import current_announcement

pytestmark = pytest.mark.django_db


def test_the_seeded_bar_is_live_on_a_fresh_database():
    bar = current_announcement()

    assert bar is not None
    assert "FREE SHIPPING" in bar.text


def test_switching_it_off_leaves_nothing_to_render():
    AnnouncementBar.objects.update(is_active=False)

    assert current_announcement() is None


def test_a_window_that_has_passed_is_not_rendered():
    AnnouncementBar.objects.update(ends_at=timezone.now() - timedelta(minutes=1))

    assert current_announcement() is None


def test_a_window_that_has_not_opened_is_not_rendered():
    AnnouncementBar.objects.update(starts_at=timezone.now() + timedelta(days=1))

    assert current_announcement() is None


def test_an_open_window_renders():
    AnnouncementBar.objects.update(
        starts_at=timezone.now() - timedelta(days=1), ends_at=timezone.now() + timedelta(days=1)
    )

    assert current_announcement() is not None


def test_the_newest_live_bar_wins():
    AnnouncementBar.objects.create(text="SALE ENDS SUNDAY")

    assert current_announcement().text == "SALE ENDS SUNDAY"


def test_a_javascript_url_is_rejected():
    bar = AnnouncementBar(text="Click me", url="javascript:alert(1)")

    with pytest.raises(ValidationError, match="site path"):
        bar.full_clean()
