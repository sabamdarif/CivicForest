"""Cookie consent gating GA4 (M9.9, L5): the banner appears only when analytics is configured,
nothing loads gtag server-side before consent, and Accept and Decline are the same button weight
so declining is no harder than accepting (no dark pattern)."""

from __future__ import annotations

import pytest
from django.test import Client, override_settings

pytestmark = pytest.mark.django_db


def test_no_banner_and_no_analytics_when_unconfigured():
    html = Client().get("/").content.decode()
    assert "data-cookie-banner" not in html  # GOOGLE_ANALYTICS_ID blank by default
    assert "googletagmanager" not in html


@override_settings(GOOGLE_ANALYTICS_ID="G-TEST123")
def test_banner_present_but_no_analytics_loaded_before_consent():
    html = Client().get("/").content.decode()
    assert "data-cookie-banner" in html
    assert 'data-ga-id="G-TEST123"' in html
    # gtag is injected by the browser only after Accept: never emitted server-side, inline or not.
    assert "googletagmanager.com/gtag/js" not in html
    assert "gtag(" not in html


@override_settings(GOOGLE_ANALYTICS_ID="G-TEST123")
def test_accept_and_decline_share_one_button_weight():
    html = Client().get("/").content.decode()
    assert '<button class="btn btn--secondary" type="button" data-cookie-decline>' in html
    assert '<button class="btn btn--secondary" type="button" data-cookie-accept>' in html
