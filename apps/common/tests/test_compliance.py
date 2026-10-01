"""Dark-pattern and disclosure sweep (M9.11), against ``02-research.md`` §5 and the §13 table.

These are the guarantees that are law, not taste: a pre-ticked consent box, a charge that appears
after commitment, or a fabricated countdown each carry a CCPA penalty. The checks here are the ones
not already pinned by a feature's own tests (marketing opt-in, cookie decline, unsubscribe), plus
the one that would silently rot: a countdown component sneaking into the codebase."""

from __future__ import annotations

from pathlib import Path

import pytest
from allauth.account.models import EmailAddress
from django.test import Client

from apps.cart.models import CartItem
from apps.catalog.services import low_stock_note
from apps.common.factories import CartFactory, ProductVariantFactory, UserFactory
from apps.orders.forms import CheckoutForm

pytestmark = pytest.mark.django_db

REPO_ROOT = Path(__file__).resolve().parents[3]


def test_the_terms_box_is_unticked_and_required():
    form = CheckoutForm(addresses=[])
    field = form.fields["accept_terms"]
    assert field.required is True
    assert not field.initial  # nothing pre-ticks it


def test_a_low_stock_message_is_derived_from_real_stock_never_fabricated():
    variant = ProductVariantFactory(stock_quantity=3)
    assert low_stock_note(variant, threshold=5) == "Only 3 left"
    variant.stock_quantity = 50
    assert low_stock_note(variant, threshold=5) == ""  # plenty: no manufactured urgency


def test_there_is_no_countdown_or_urgency_timer_anywhere_in_the_source():
    # §13: "there is no countdown component in the codebase at all." A grep guards that claim.
    offenders = []
    for base in ("templates", "static", "apps"):
        for path in (REPO_ROOT / base).rglob("*"):
            if path.suffix not in {".html", ".js", ".css", ".py"} or "tests" in path.parts:
                continue
            if "countdown" in path.read_text(encoding="utf-8", errors="ignore").lower():
                offenders.append(str(path.relative_to(REPO_ROOT)))
    assert offenders == []


def test_checkout_shows_every_charge_before_the_pay_button():
    user = UserFactory()
    EmailAddress.objects.create(user=user, email=user.email, primary=True, verified=True)
    variant = ProductVariantFactory(stock_quantity=5)
    cart = CartFactory(user=user)
    CartItem.objects.create(cart=cart, variant=variant, quantity=1)

    client = Client()
    client.force_login(user)
    body = client.get("/checkout/").content.decode()

    for label in ("Subtotal", "Shipping", "Total"):
        assert label in body, label
    # Every charge is visible above the commit, so nothing is sprung after it.
    assert body.index("Subtotal") < body.index("Pay")
    # The terms box is unticked on first render.
    at = body.index('name="accept_terms"')
    assert "checked" not in body[at - 80 : at + 80]


def test_the_grievance_page_is_reachable_and_linked_from_the_footer():
    assert Client().get("/grievance-redressal/").status_code == 200
    home = Client().get("/").content.decode()
    assert "/grievance-redressal/" in home


def test_the_newsletter_footer_form_pre_ticks_no_consent():
    home = Client().get("/").content.decode()
    assert 'action="/newsletter/subscribe/"' in home
    assert "checked" not in home[home.index("newsletter") : home.index("newsletter") + 600]
