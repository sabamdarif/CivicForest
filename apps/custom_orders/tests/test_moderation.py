"""Design moderation and the saved-designs page (M7.6, M7.10)."""

import pytest
from django.core import mail
from django.test import Client

from apps.common.email import send_design_review_email
from apps.custom_orders.models import CustomDesignOrder, DesignUpload

pytestmark = pytest.mark.django_db


def _design(user, **kw):
    return DesignUpload.objects.create(
        user=user,
        r2_key_print="designs/print/x.png",
        status=DesignUpload.Status.READY,
        review_status=DesignUpload.ReviewStatus.FLAGGED,
        width_px=1000,
        height_px=1000,
        **kw,
    )


def test_review_email_sent_on_approve(user):
    design = _design(user)
    assert send_design_review_email(str(design.id), "approved") == "sent"
    assert len(mail.outbox) == 1
    assert user.email in mail.outbox[0].to


def test_review_email_includes_reason_on_reject(user):
    design = _design(user, review_reason="Trademarked logo")
    send_design_review_email(str(design.id), "rejected")
    assert "Trademarked logo" in mail.outbox[0].body


def test_designs_page_lists_and_deletes(user):
    design = _design(user)
    client = Client()
    client.force_login(user)

    assert client.get("/account/designs/").status_code == 200

    resp = client.post(
        "/account/designs/", {"action": "delete", "design_id": str(design.id)}, follow=True
    )
    assert resp.status_code == 200
    assert not DesignUpload.objects.filter(id=design.id).exists()


def test_design_in_an_order_cannot_be_deleted(user, variant, paid_order):
    design = _design(user)
    CustomDesignOrder.objects.create(
        user=user, order=paid_order, blank_variant=variant, design_upload=design
    )
    client = Client()
    client.force_login(user)

    client.post("/account/designs/", {"action": "delete", "design_id": str(design.id)})
    assert DesignUpload.objects.filter(id=design.id).exists()
