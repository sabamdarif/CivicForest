import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.accounts.models import Address

pytestmark = pytest.mark.django_db

ADDRESS = {
    "kind": "shipping",
    "full_name": "Test Buyer",
    "phone": "9999999999",
    "line1": "1 MG Road",
    "line2": "",
    "city": "Bengaluru",
    "state": "Karnataka",
    "postal_code": "560001",
    "country": "IN",
    "is_default": True,
}


def _client(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def test_oauth_only_user_cannot_update_without_recent_auth(monkeypatch):
    user = get_user_model().objects.create_user(email="oauth@example.com")
    user.set_unusable_password()
    user.save(update_fields=["password"])
    address = Address.objects.create(user=user, **ADDRESS)
    monkeypatch.setattr("apps.accounts.views.did_recently_authenticate", lambda request: False)

    response = _client(user).patch(
        f"/api/v1/account/addresses/{address.id}", {"city": "Mysuru"}, format="json"
    )

    assert response.status_code == 403
    assert response.data["error"]["code"] == "oauth_reauthentication_required"
    address.refresh_from_db()
    assert address.city == "Bengaluru"


def test_address_create_requires_recent_auth(monkeypatch):
    user = get_user_model().objects.create_user(
        email="password@example.com", password="pw-1234567!"
    )
    monkeypatch.setattr("apps.accounts.views.did_recently_authenticate", lambda request: False)

    response = _client(user).post("/api/v1/account/addresses", ADDRESS, format="json")

    assert response.status_code == 403
    assert response.data["error"]["code"] == "reauthentication_required"
    assert Address.objects.filter(user=user).count() == 0


def test_password_user_with_recent_auth_can_create(monkeypatch):
    user = get_user_model().objects.create_user(email="recent@example.com", password="pw-1234567!")
    monkeypatch.setattr("apps.accounts.views.did_recently_authenticate", lambda request: True)

    response = _client(user).post("/api/v1/account/addresses", ADDRESS, format="json")

    assert response.status_code == 201
    assert Address.objects.filter(user=user, city="Bengaluru").exists()
