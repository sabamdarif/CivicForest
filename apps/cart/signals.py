"""Merge a guest's session cart into their user cart on login.

The guest cart is keyed on the session key the visitor browsed with, and that key is gone by
the time this runs: allauth calls ``adapter.login()``, which is Django's ``login()`` and rotates
the key, before it sends ``user_logged_in`` from ``post_login``. Session *data* survives that
rotation, so ``services.get_or_create_cart`` stashes the key as it hands a guest their cart and
this reads it back. Anything that only looked at ``request.session.session_key`` here would
silently merge nothing.
"""

from __future__ import annotations

from allauth.account.signals import user_logged_in
from django.dispatch import receiver

from . import services


@receiver(user_logged_in)
def merge_cart_on_login(sender, request, user, **kwargs):
    session = getattr(request, "session", None)
    if session is None:
        return
    session_key = session.pop(services.GUEST_CART_KEY, None)
    if session_key:
        services.merge_guest_cart_into_user(session_key, user)
