"""Jobs and outbound email (M8.13): the bearer-gated cron endpoints, the staff-gated run-now and
resend, and the OutboundEmail ledger.

The cron endpoint is adversarial: a missing or wrong bearer must not run anything, and a valid one
writes exactly one JobRun row. Run-now and resend are gated per permission.
"""

import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse

from apps.common.email import send_order_email
from apps.common.factories import OrderFactory, StaffUserFactory, login_staff_with_mfa
from apps.common.models import JobRun, OutboundEmail

pytestmark = pytest.mark.django_db


def _staff_with(client, *codenames):
    user = StaffUserFactory()
    for codename in codenames:
        user.user_permissions.add(Permission.objects.get(codename=codename))
    login_staff_with_mfa(client, user=user)
    return user


def test_cron_rejects_missing_bearer(client, settings):
    settings.CRON_SECRET = "s3cret"
    response = client.post(reverse("cron_run", kwargs={"name": "expire_carts"}))
    assert response.status_code == 401
    assert not JobRun.objects.exists()


def test_cron_rejects_wrong_bearer(client, settings):
    settings.CRON_SECRET = "s3cret"
    response = client.post(
        reverse("cron_run", kwargs={"name": "expire_carts"}), HTTP_AUTHORIZATION="Bearer nope"
    )
    assert response.status_code == 401
    assert not JobRun.objects.exists()


def test_cron_runs_job_with_right_bearer(client, settings):
    settings.CRON_SECRET = "s3cret"
    response = client.post(
        reverse("cron_run", kwargs={"name": "expire_carts"}), HTTP_AUTHORIZATION="Bearer s3cret"
    )
    assert response.status_code == 200
    run = JobRun.objects.get()
    assert run.name == "expire_carts"
    assert run.status == JobRun.Status.DONE


def test_cron_unknown_job_is_404(client, settings):
    settings.CRON_SECRET = "s3cret"
    response = client.post(
        reverse("cron_run", kwargs={"name": "no-such-job"}), HTTP_AUTHORIZATION="Bearer s3cret"
    )
    assert response.status_code == 404


def test_panel_requires_view_permission(client):
    _staff_with(client)
    assert client.get(reverse("backoffice:jobs")).status_code == 404


def test_run_now_requires_add_permission(client):
    _staff_with(client, "view_jobrun")  # can look, cannot run
    response = client.post(reverse("backoffice:job_run"), {"name": "expire_carts"})
    assert response.status_code == 404
    assert not JobRun.objects.exists()


def test_run_now_runs_the_job(client):
    _staff_with(client, "add_jobrun")
    client.post(reverse("backoffice:job_run"), {"name": "expire_carts"})
    assert JobRun.objects.get().name == "expire_carts"


def test_sending_an_email_records_a_ledger_row(client):
    order = OrderFactory()
    result = send_order_email(str(order.pk), "confirmation")
    assert result == "sent"
    row = OutboundEmail.objects.get()
    assert row.template == "order:confirmation"
    assert row.status == OutboundEmail.Status.SENT


def test_resend_requires_change_permission(client):
    order = OrderFactory()
    send_order_email(str(order.pk), "confirmation")
    row = OutboundEmail.objects.get()
    _staff_with(client, "view_jobrun")  # no change_outboundemail

    response = client.post(reverse("backoffice:email_resend", kwargs={"pk": row.pk}))

    assert response.status_code == 404
    assert OutboundEmail.objects.count() == 1


def test_resend_sends_again(client):
    order = OrderFactory()
    send_order_email(str(order.pk), "confirmation")
    row = OutboundEmail.objects.get()
    _staff_with(client, "change_outboundemail")

    client.post(reverse("backoffice:email_resend", kwargs={"pk": row.pk}))

    assert OutboundEmail.objects.count() == 2
