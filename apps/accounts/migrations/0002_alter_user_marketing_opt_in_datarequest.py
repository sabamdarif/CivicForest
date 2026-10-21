"""Add account consent, data requests, and address invariants."""

import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def normalise_default_addresses(apps, schema_editor):
    Address = apps.get_model("accounts", "Address")
    duplicates = (
        Address.objects.filter(is_default=True)
        .values_list("user_id", flat=True)
        .order_by("user_id")
    )
    seen = set()
    for user_id in duplicates.iterator():
        if user_id in seen:
            continue
        seen.add(user_id)
        defaults = Address.objects.filter(user_id=user_id, is_default=True).order_by(
            "created_at", "id"
        )
        keeper = defaults.first()
        if keeper:
            defaults.exclude(pk=keeper.pk).update(is_default=False)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="user",
            name="marketing_opt_in",
            field=models.BooleanField(
                default=False,
                help_text=(
                    "Explicit opt-in for marketing email, unticked by default (DPDP Act, J9)."
                ),
            ),
        ),
        migrations.CreateModel(
            name="DataRequest",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "kind",
                    models.CharField(
                        choices=[("export", "Export"), ("erasure", "Erasure")],
                        max_length=10,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("open", "Open"),
                            ("done", "Done"),
                            ("refused", "Refused"),
                        ],
                        default="open",
                        max_length=10,
                    ),
                ),
                ("note", models.TextField(blank=True)),
                ("handled_at", models.DateTimeField(blank=True, null=True)),
                (
                    "handled_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="+",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="data_requests",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.RunPython(normalise_default_addresses, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="address",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_default", True)),
                fields=("user",),
                name="accounts_one_default_address",
            ),
        ),
        migrations.AddConstraint(
            model_name="datarequest",
            constraint=models.UniqueConstraint(
                condition=models.Q(("kind", "erasure"), ("status", "open")),
                fields=("user",),
                name="accounts_one_open_erasure",
            ),
        ),
    ]
