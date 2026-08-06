from django.test import Client, override_settings


def test_healthz_hides_endpoint_without_token():
    response = Client().get("/healthz")

    assert response.status_code == 404


@override_settings(HEALTH_CHECK_TOKEN="probe-secret")
def test_healthz_accepts_internal_token():
    response = Client().get("/healthz", HTTP_X_HEALTH_TOKEN="probe-secret")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@override_settings(HEALTH_CHECK_TOKEN="probe-secret")
def test_readyz_rejects_wrong_token_before_dependency_checks():
    response = Client().get("/readyz", HTTP_X_HEALTH_TOKEN="wrong")

    assert response.status_code == 404
