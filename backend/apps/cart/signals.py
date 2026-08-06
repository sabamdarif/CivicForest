"""Merge a guest's session cart into their user cart on login.

allauth fires ``user_logged_in`` after the session is authenticated. The guest cart was
keyed to the pre-login session key, so we capture it from the request session and fold
it in (summing quantities, re-capping at stock) via the service layer."""

from __future__ import annotations

from allauth.account.signals import user_logged_in
from django.dispatch import receiver

from . import services


@receiver(user_logged_in)
def merge_cart_on_login(sender, request, user, **kwargs):
    session_key = getattr(getattr(request, "session", None), "session_key", None)
    if session_key:
        services.merge_guest_cart_into_user(session_key, user)
    if getattr(request, "session", None) is not None:
        request.session.cycle_key()
