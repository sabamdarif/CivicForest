import pytest
from django.contrib.auth import get_user_model

pytestmark = pytest.mark.django_db

User = get_user_model()


def test_create_user_uses_email_as_identifier():
    user = User.objects.create_user(email="Buyer@Example.com", password="s3cret-pass!")
    # Email domain is normalized by allauth/Django's normalize_email.
    assert user.email == "Buyer@example.com"
    assert user.check_password("s3cret-pass!")
    assert user.is_staff is False


def test_create_superuser_flags():
    admin = User.objects.create_superuser(email="admin@example.com", password="x-pass-123!")
    assert admin.is_staff and admin.is_superuser


def test_user_str_is_email():
    user = User.objects.create_user(email="a@b.com", password="pw-123456!")
    assert str(user) == "a@b.com"
