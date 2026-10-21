"""Admin hardening (M8.15, O12): auditlog coverage, the back-office audit viewer, and no bulk
delete on orders.

The audit surfaces (StockAdjustment, JobRun, OutboundEmail) are deliberately not audited: they are
logs themselves, so auditing them is noise.
"""

import pytest
from auditlog.registry import auditlog
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import Permission
from django.test import RequestFactory
from django.urls import reverse

from apps.accounts.models import User
from apps.common.factories import StaffUserFactory, UserFactory, login_staff_with_mfa
from apps.common.models import JobRun, OutboundEmail, StockAdjustment
from apps.custom_orders.models import CustomDesignOrder
from apps.orders.admin import OrderAdmin
from apps.orders.models import Order
from apps.payments.models import Payment

pytestmark = pytest.mark.django_db


def _staff_with(client, *codenames):
    user = StaffUserFactory()
    for codename in codenames:
        user.user_permissions.add(Permission.objects.get(codename=codename))
    login_staff_with_mfa(client, user=user)
    return user


def test_audit_viewer_requires_permission(client):
    _staff_with(client)
    assert client.get(reverse("backoffice:audit")).status_code == 404


def test_audit_viewer_shows_a_change(client):
    user = UserFactory(email="audited@example.com")
    user.first_name = "Changed"
    user.save()
    # "view_logentry" exists for both admin.LogEntry and auditlog.LogEntry, so qualify it.
    staff = StaffUserFactory()
    staff.user_permissions.add(
        Permission.objects.get(content_type__app_label="auditlog", codename="view_logentry")
    )
    login_staff_with_mfa(client, user=staff)

    body = client.get(reverse("backoffice:audit")).content.decode()

    assert "audited@example.com" in body


def test_domain_models_are_audited():
    for model in (User, Payment, CustomDesignOrder):
        assert auditlog.contains(model), f"{model.__name__} should be audited (O12)"


def test_log_surfaces_are_not_audited():
    for model in (StockAdjustment, JobRun, OutboundEmail):
        assert not auditlog.contains(model), f"{model.__name__} is a log; auditing it is noise"


def test_order_admin_has_no_bulk_delete():
    admin = OrderAdmin(Order, AdminSite())
    request = RequestFactory().get("/")
    request.user = StaffUserFactory(is_superuser=True)
    assert "delete_selected" not in admin.get_actions(request)
