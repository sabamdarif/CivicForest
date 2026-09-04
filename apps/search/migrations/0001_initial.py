"""The search tables, plus the pg_trgm extension the typo-tolerant path needs.

`TrigramExtension` is a no-op on any backend that is not Postgres, so the same migration runs
against the SQLite database local development and the offline test run use. On Postgres it needs
rights to `CREATE EXTENSION`, which A9's manual `migrate` gate is where that is exercised.
"""

import uuid

import django.contrib.postgres.indexes
import django.contrib.postgres.search
import django.db.models.deletion
from django.contrib.postgres.operations import TrigramExtension
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("catalog", "0005_collection_sizechart_and_compliance_fields"),
    ]

    operations = [
        TrigramExtension(),
        migrations.CreateModel(
            name="SearchQueryLog",
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
                ("query", models.CharField(db_index=True, max_length=60)),
                ("result_count", models.PositiveIntegerField(default=0)),
                ("session_key", models.CharField(blank=True, max_length=64)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="SearchSynonym",
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
                ("term", models.CharField(max_length=60, unique=True)),
                (
                    "expansion",
                    models.CharField(
                        help_text="Comma-separated equivalents, e.g. tshirt, tee, tees",
                        max_length=240,
                    ),
                ),
                ("is_active", models.BooleanField(default=True)),
            ],
            options={
                "ordering": ["term"],
            },
        ),
        migrations.CreateModel(
            name="SearchDocument",
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
                    "vector",
                    django.contrib.postgres.search.SearchVectorField(
                        editable=False, null=True
                    ),
                ),
                ("text", models.TextField(blank=True, editable=False)),
                ("is_stale", models.BooleanField(default=True)),
                (
                    "product",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="search_document",
                        to="catalog.product",
                    ),
                ),
            ],
            options={
                "ordering": ["-created_at"],
                "indexes": [
                    django.contrib.postgres.indexes.GinIndex(
                        fields=["vector"], name="search_document_vector_gin"
                    )
                ],
            },
        ),
    ]
