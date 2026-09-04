"""The styleguide answers staff and nobody else.

A 404 rather than a redirect is the point: allauth is unmounted until M5, so there is
nowhere to redirect to, and a page you may not see should not confirm that it exists.
"""

import pytest

from apps.common.factories import StaffUserFactory, UserFactory

pytestmark = pytest.mark.django_db

URL = "/styleguide/"


def test_anonymous_is_told_nothing(client):
    assert client.get(URL).status_code == 404


def test_a_signed_in_customer_is_told_nothing(client):
    client.force_login(UserFactory())

    assert client.get(URL).status_code == 404


def test_staff_get_every_component(client):
    client.force_login(StaffUserFactory())

    response = client.get(URL)

    assert response.status_code == 200
    body = response.content.decode()
    for marker in (
        "btn--gold",
        "field__error",
        "search-bar__input",
        "badge--sale",
        "product-card",
        "price__mrp",
        "swatch--out",
        "accordion__summary",
        'class="modal"',
        'class="drawer"',
        "data-toast",
        "breadcrumbs__list",
        "pagination__list",
        "stepper__input",
        "empty__title",
        "skeleton",
    ):
        assert marker in body, marker


def test_debug_opens_it_for_local_css_work(client, settings):
    # Nothing can sign in through a browser until M5 mounts allauth, and the production
    # settings force DEBUG off.
    settings.DEBUG = True

    assert client.get(URL).status_code == 200
