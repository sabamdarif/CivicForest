"""Default-address invariants shared by storefront and API writes."""

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, close_old_connections, connection, transaction

from apps.accounts.models import Address
from apps.accounts.services import delete_address, save_address
from apps.common.factories import UserFactory

pytestmark = pytest.mark.django_db


def _address(user=None, *, name="Buyer", default=False, line="1 MG Road"):
    return Address(
        user=user,
        full_name=name,
        phone="9999999999",
        line1=line,
        city="Bengaluru",
        state="Karnataka",
        postal_code="560001",
        is_default=default,
    )


def test_first_address_becomes_default():
    user = UserFactory()

    address = save_address(user, _address())

    assert address.is_default is True
    assert Address.objects.get(pk=address.pk).is_default is True


def test_new_default_demotes_existing_default():
    user = UserFactory()
    first = save_address(user, _address(default=True))

    second = save_address(user, _address(default=True, line="2 MG Road"))

    first.refresh_from_db()
    assert first.is_default is False
    assert second.is_default is True


def test_editing_nondefault_keeps_existing_default():
    user = UserFactory()
    current = save_address(user, _address(default=True))
    other = save_address(user, _address(line="2 MG Road"))
    other.city = "Mysuru"

    save_address(user, other)

    current.refresh_from_db()
    other.refresh_from_db()
    assert current.is_default is True
    assert other.is_default is False
    assert other.city == "Mysuru"


def test_only_default_cannot_be_unset():
    user = UserFactory()
    address = save_address(user, _address(default=True))
    address.is_default = False

    save_address(user, address)

    address.refresh_from_db()
    assert address.is_default is True


def test_deleting_default_promotes_newest_survivor():
    user = UserFactory()
    current = save_address(user, _address(default=True))
    older = save_address(user, _address(line="2 MG Road"))
    newest = save_address(user, _address(line="3 MG Road"))

    delete_address(user, current)

    older.refresh_from_db()
    newest.refresh_from_db()
    assert older.is_default is False
    assert newest.is_default is True


def test_address_service_rejects_another_users_address():
    owner = UserFactory()
    attacker = UserFactory()
    address = save_address(owner, _address(default=True))
    address.city = "Mysuru"

    with pytest.raises(Address.DoesNotExist):
        save_address(attacker, address)

    address.refresh_from_db()
    assert address.city == "Bengaluru"


def test_database_rejects_two_defaults_for_one_user():
    user = UserFactory()
    _address(user=user, default=True).save()

    with pytest.raises(IntegrityError), transaction.atomic():
        _address(user=user, default=True, line="2 MG Road").save()


def _concurrent_create(user_id, line, barrier):
    close_old_connections()
    try:
        user = get_user_model().objects.get(pk=user_id)
        barrier.wait()
        return save_address(user, _address(default=True, line=line)).pk
    finally:
        close_old_connections()


@pytest.mark.django_db(transaction=True)
def test_concurrent_first_addresses_leave_one_default():
    if connection.vendor != "postgresql":
        pytest.skip("Row-lock concurrency requires PostgreSQL")
    user = UserFactory()
    barrier = Barrier(2)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(_concurrent_create, user.pk, f"{number} MG Road", barrier)
            for number in (1, 2)
        ]
        for future in futures:
            future.result()

    addresses = Address.objects.filter(user=user)
    assert addresses.count() == 2
    assert addresses.filter(is_default=True).count() == 1
