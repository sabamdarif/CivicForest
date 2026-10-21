"""Contact form and support inbox (M9.7): a plain no-JS POST stores the message and notifies
support, the honeypot silently drops a bot, and marking a message handled needs the change
permission (a view-only role is refused)."""

from __future__ import annotations

import pytest
from django.contrib.auth.models import Permission
from django.core import mail
from django.test import Client
from django.urls import reverse

from apps.common.factories import StaffUserFactory, login_staff_with_mfa
from apps.content.models import ContactMessage

pytestmark = pytest.mark.django_db


def _staff_with(client, *codenames):
    user = StaffUserFactory()
    for codename in codenames:
        user.user_permissions.add(Permission.objects.get(codename=codename))
    login_staff_with_mfa(client, user=user)
    return user


def test_the_contact_page_renders():
    assert Client().get("/contact/").status_code == 200


def test_a_valid_message_is_stored_and_support_is_notified():
    resp = Client().post(
        "/contact/",
        {
            "name": "Ravi",
            "email": "ravi@example.com",
            "order_number": "CF-ABCD1234",
            "subject": "Where is my order?",
            "message": "It has been a week.",
        },
    )
    assert resp.status_code == 302
    msg = ContactMessage.objects.get(email="ravi@example.com")
    assert msg.order_number == "CF-ABCD1234"
    assert len(mail.outbox) == 1  # support notified


def test_a_tripped_honeypot_is_dropped_silently():
    resp = Client().post(
        "/contact/",
        {
            "name": "Bot",
            "email": "bot@example.com",
            "subject": "cheap watches",
            "message": "spam",
            "website": "http://spam.example",  # honeypot filled
        },
    )
    assert resp.status_code == 302  # looks like success
    assert not ContactMessage.objects.filter(email="bot@example.com").exists()
    assert mail.outbox == []


# ── Back-office inbox ───────────────────────────────────────────────────────────
def _message():
    return ContactMessage.objects.create(
        name="Ravi", email="ravi@example.com", subject="Help", message="please"
    )


def test_inbox_requires_view_permission():
    client = Client()
    _staff_with(client)  # no content.view_contactmessage
    assert client.get(reverse("backoffice:messages")).status_code == 404


def test_a_view_only_role_cannot_mark_handled():
    msg = _message()
    client = Client()
    _staff_with(client, "view_contactmessage")  # no change
    resp = client.post(
        reverse("backoffice:message_detail", kwargs={"pk": msg.id}),
        {"action": "mark_handled", "internal_note": "x"},
    )
    assert resp.status_code == 404
    msg.refresh_from_db()
    assert msg.handled_at is None


def test_a_supporter_can_mark_handled_and_note():
    msg = _message()
    client = Client()
    _staff_with(client, "view_contactmessage", "change_contactmessage")
    resp = client.post(
        reverse("backoffice:message_detail", kwargs={"pk": msg.id}),
        {"action": "mark_handled", "internal_note": "Refunded and replied."},
    )
    assert resp.status_code == 302
    msg.refresh_from_db()
    assert msg.handled_at is not None
    assert msg.internal_note == "Refunded and replied."
