"""`bootstrap_roles` builds the four O11 groups and is safe to re-run."""

import pytest
from django.contrib.auth.models import Group, Permission
from django.core.management import call_command

pytestmark = pytest.mark.django_db


def _run():
    call_command("bootstrap_roles")


def test_creates_the_four_roles():
    _run()

    assert set(Group.objects.values_list("name", flat=True)) >= {
        "Owner",
        "Manager",
        "Fulfilment",
        "Support",
    }


def test_owner_gets_everything():
    _run()

    owner = Group.objects.get(name="Owner")
    assert owner.permissions.count() == Permission.objects.count()


def test_support_is_orders_read_only():
    _run()

    support = Group.objects.get(name="Support")
    codenames = set(support.permissions.values_list("codename", flat=True))
    assert "view_order" in codenames
    assert "change_order" not in codenames
    assert "transition_order" not in codenames
    assert "refund_order" not in codenames


def test_fulfilment_can_move_orders_but_not_refund():
    _run()

    fulfilment = Group.objects.get(name="Fulfilment")
    codenames = set(fulfilment.permissions.values_list("codename", flat=True))
    assert {"transition_order", "change_order"} <= codenames
    assert "refund_order" not in codenames


def test_manager_cannot_administer_staff():
    _run()

    manager = Group.objects.get(name="Manager")
    perms = manager.permissions.select_related("content_type")
    user_writes = [
        p
        for p in perms
        if p.content_type.app_label == "accounts"
        and p.content_type.model == "user"
        and p.codename.startswith(("add_", "change_", "delete_"))
    ]
    assert user_writes == []
    # No auth-group or permission administration either.
    assert not perms.filter(content_type__app_label="auth").exists()


def test_rerun_is_idempotent():
    _run()
    owner_before = set(Group.objects.get(name="Owner").permissions.values_list("id", flat=True))

    _run()

    assert Group.objects.filter(name="Owner").count() == 1
    owner_after = set(Group.objects.get(name="Owner").permissions.values_list("id", flat=True))
    assert owner_before == owner_after
