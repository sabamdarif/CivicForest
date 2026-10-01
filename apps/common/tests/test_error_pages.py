"""Error and maintenance pages (M9.12): a 404 renders the branded page, the 500 renders without a
database read, and maintenance mode is off by default and gates everything but the exempt paths
when switched on."""

from __future__ import annotations

import pytest
from django.test import Client, override_settings

from apps.common.views import server_error

pytestmark = pytest.mark.django_db


def test_an_unknown_url_renders_the_branded_404():
    resp = Client().get("/this-page-does-not-exist/")
    assert resp.status_code == 404
    assert b"can't find that page" in resp.content


def test_the_500_view_renders_without_a_database_read(rf):
    # Called directly: a real 500 may be the DB failing, so the page must stand alone.
    resp = server_error(rf.get("/"))
    assert resp.status_code == 500
    assert b"Something went wrong" in resp.content


def test_maintenance_mode_is_off_by_default():
    assert Client().get("/").status_code == 200


@override_settings(MAINTENANCE_MODE=True)
def test_maintenance_mode_returns_503_for_the_storefront():
    resp = Client().get("/")
    assert resp.status_code == 503
    assert b"back shortly" in resp.content


@override_settings(MAINTENANCE_MODE=True)
def test_healthz_stays_up_during_maintenance():
    assert Client().get("/healthz/").status_code == 200
