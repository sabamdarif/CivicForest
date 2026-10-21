"""Create a dev test user and admin superuser. Refuses to run with DEBUG off.

Usage: ``python manage.py seed_dev_users``  (idempotent)

Logins:
  admin@civicforest.local / admin12345  (superuser — /admin works)
  test@civicforest.local  / test12345   (regular customer)
"""

from allauth.account.models import EmailAddress
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

USERS = [
    ("admin@civicforest.local", "admin12345", True),
    ("test@civicforest.local", "test12345", False),
]


class Command(BaseCommand):
    help = "Seed a dev admin + test user (DEBUG only)."

    def handle(self, *args, **options):
        if not settings.DEBUG:
            raise CommandError("Dev-only command: refusing to create weak users with DEBUG=False.")

        User = get_user_model()
        for email, password, is_admin in USERS:
            user, created = User.objects.get_or_create(
                email=email,
                defaults={"is_staff": is_admin, "is_superuser": is_admin},
            )
            user.set_password(password)
            user.is_staff = is_admin
            user.is_superuser = is_admin
            user.save()
            # Mark email verified so allauth login works without a mail server.
            EmailAddress.objects.update_or_create(
                user=user, email=email, defaults={"verified": True, "primary": True}
            )
            self.stdout.write(f"{'created' if created else 'updated'}: {email} / {password}")
