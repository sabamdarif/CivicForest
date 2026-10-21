"""The header overlay's markup contract (M3.8).

The script is not exercised here: what matters in a template test is that the icon is still a
link, that the field is still a form, and that the payload the script reads exists. Those three
are what make the overlay an enhancement rather than a requirement (P6, D7).
"""

import pytest

from apps.search.models import MAX_QUERY_LENGTH

pytestmark = pytest.mark.django_db


@pytest.fixture
def body(client):
    return client.get("/").content.decode()


def test_the_icon_is_a_link_before_it_is_an_overlay(body):
    # With no JavaScript this navigates; modal.js cancels the click and opens the dialog instead.
    assert '<a class="icon-btn" href="/search/" aria-label="Search" data-dialog-open=' in body


def test_the_overlay_is_a_dialog_so_the_element_owns_the_hard_parts(body):
    # Focus trap, inert page, backdrop and Escape are the element's, not a script's.
    assert '<dialog class="modal search-overlay" id="search-overlay"' in body
    assert 'data-dialog-close="search-overlay"' in body


def test_the_field_is_a_get_form_that_submits_to_the_results_page(body):
    assert '<form class="search-overlay__form" method="get" action="/search/"' in body
    assert 'name="q"' in body
    assert f'maxlength="{MAX_QUERY_LENGTH}"' in body


def test_the_overlay_announces_its_result_count(body):
    assert 'role="status" data-search-count' in body


def test_the_overlay_is_on_every_page_because_the_header_is(client, catalogue):
    from django.core.management import call_command

    call_command("reindex_search")
    for url in ("/", "/shop/", "/product/plain-tee/", "/search/?q=tee", "/collections/"):
        assert 'id="search-overlay"' in client.get(url).content.decode(), url
