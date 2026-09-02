"""Both template engines render and share one set of stylesheets.

Jinja2 renders the pages this project owns; the Django Template Language renders what
allauth and the admin ship. A page that reaches a variable the environment does not
define fails here, because the test settings use StrictUndefined.
"""

import pytest
from django.template.loader import get_template
from django.test import Client

STYLESHEETS = ("css/tokens.css", "css/base.css", "css/components.css", "css/layout.css")


@pytest.mark.django_db
def test_home_renders_through_the_jinja2_engine():
    # The chrome reads the announcement bar, so rendering any page now touches the database.
    response = Client().get("/")

    assert response.status_code == 200
    body = response.content.decode()
    assert "Premium menswear" in body
    assert "FREE SHIPPING ON ALL ORDERS ABOVE ₹999" in body
    for sheet in STYLESHEETS:
        assert sheet in body


def test_the_django_engine_shell_loads_the_same_stylesheets():
    rendered = get_template("base.html", using="django").render({})

    for sheet in STYLESHEETS:
        assert sheet in rendered
