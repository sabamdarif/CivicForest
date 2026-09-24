"""Design review queue (M8.6): the view gate, the flagged-vs-failed filters, and the guarded
approve/reject/resubmit actions surfacing the M7 moderation flow.

Authz is the adversarial surface here: a view-only role can open the queue but cannot approve,
reject or resubmit.
"""

import pytest
from django.contrib.auth.models import Permission
from django.core import mail
from django.urls import reverse

from apps.common.factories import OrderFactory, StaffUserFactory, UserFactory, login_staff_with_mfa
from apps.custom_orders.models import CustomDesignOrder, DesignUpload
from apps.orders.models import Order

pytestmark = pytest.mark.django_db


def _staff_with(client, *codenames):
    user = StaffUserFactory()
    for codename in codenames:
        user.user_permissions.add(Permission.objects.get(codename=codename))
    login_staff_with_mfa(client, user=user)
    return user


def _design(**kwargs):
    kwargs.setdefault("user", UserFactory())
    kwargs.setdefault("status", DesignUpload.Status.READY)
    kwargs.setdefault("review_status", DesignUpload.ReviewStatus.FLAGGED)
    return DesignUpload.objects.create(**kwargs)


def test_queue_requires_view_permission(client):
    _staff_with(client)

    assert client.get(reverse("backoffice:designs")).status_code == 404


def test_queue_defaults_to_flagged(client):
    flagged = _design()
    approved = _design(review_status=DesignUpload.ReviewStatus.APPROVED)
    _staff_with(client, "view_designupload")

    body = client.get(reverse("backoffice:designs")).content.decode()

    assert str(flagged.id)[:8] in body
    assert str(approved.id)[:8] not in body


def test_failed_qikink_filter(client):
    good = _design(review_status=DesignUpload.ReviewStatus.APPROVED)
    bad_design = _design(review_status=DesignUpload.ReviewStatus.APPROVED)
    CustomDesignOrder.objects.create(
        user=bad_design.user,
        design_upload=bad_design,
        submit_status=CustomDesignOrder.SubmitStatus.FAILED,
    )
    _staff_with(client, "view_designupload")

    body = client.get(reverse("backoffice:designs"), {"submit": "failed"}).content.decode()

    assert str(bad_design.id)[:8] in body
    assert str(good.id)[:8] not in body


def test_view_only_role_cannot_approve(client):
    design = _design()
    _staff_with(client, "view_designupload")

    url = reverse("backoffice:design_action", kwargs={"pk": design.id})
    response = client.post(url, {"action": "approve"})

    assert response.status_code == 404
    design.refresh_from_db()
    assert design.review_status == DesignUpload.ReviewStatus.FLAGGED


def test_approve_sets_status_and_emails(client):
    design = _design()
    _staff_with(client, "change_designupload")

    url = reverse("backoffice:design_action", kwargs={"pk": design.id})
    client.post(url, {"action": "approve"})

    design.refresh_from_db()
    assert design.review_status == DesignUpload.ReviewStatus.APPROVED
    assert len(mail.outbox) == 1


def test_reject_records_reason(client):
    design = _design()
    _staff_with(client, "change_designupload")

    url = reverse("backoffice:design_action", kwargs={"pk": design.id})
    client.post(url, {"action": "reject", "reason": "trademark"})

    design.refresh_from_db()
    assert design.review_status == DesignUpload.ReviewStatus.REJECTED
    assert design.review_reason == "trademark"


def test_resubmit_needs_its_own_permission(client):
    design = _design()
    _staff_with(client, "change_designupload")  # not change_customdesignorder

    url = reverse("backoffice:design_action", kwargs={"pk": design.id})
    assert client.post(url, {"action": "resubmit"}).status_code == 404


def test_resubmit_of_unsubmittable_line_is_a_no_op(client):
    # A flagged (not reviewed-ok) line is not submittable, so no Qikink call is attempted.
    order = OrderFactory(status=Order.Status.PAID)
    design = _design()
    CustomDesignOrder.objects.create(
        user=design.user,
        order=order,
        design_upload=design,
        submit_status=CustomDesignOrder.SubmitStatus.FAILED,
    )
    _staff_with(client, "change_customdesignorder")

    url = reverse("backoffice:design_action", kwargs={"pk": design.id})
    response = client.post(url, {"action": "resubmit"})

    assert response.status_code == 302  # redirects back with a "nothing to resubmit" message


def test_detail_renders_without_print_file(client):
    design = _design()
    _staff_with(client, "view_designupload")

    url = reverse("backoffice:design_detail", kwargs={"pk": design.id})
    body = client.get(url).content.decode()

    assert "No print-ready file yet" in body
