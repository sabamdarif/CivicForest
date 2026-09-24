"""Serializers for the custom-print API.

The upload path never carries image bytes: the client declares a content type and size, gets
a presigned PUT, and uploads straight to R2 (M7.2). These serializers bound the declared
values and shape the design rows read back to the account area."""

from __future__ import annotations

from decimal import Decimal

from rest_framework import serializers

from apps.common import r2

from .models import CustomDesignOrder, DesignUpload
from .uploads import ALLOWED_MIME


class UploadUrlSerializer(serializers.Serializer):
    """Input for minting a presigned upload URL. The real bytes are validated out of band by
    the sanitise step; here only the client's declared type and size are bounded."""

    content_type = serializers.ChoiceField(choices=sorted(ALLOWED_MIME))
    bytes = serializers.IntegerField(min_value=1)

    def validate_bytes(self, value):
        from django.conf import settings

        cap = getattr(settings, "DESIGN_UPLOAD_MAX_BYTES", 15 * 1024 * 1024)
        if value > cap:
            raise serializers.ValidationError(f"File is too large (max {cap // (1024 * 1024)} MB).")
        return value


class DesignUploadSerializer(serializers.ModelSerializer):
    """Read shape for a design. The R2 keys are never exposed; the preview is a short-lived
    signed GET so a raw design is never publicly addressable."""

    preview_url = serializers.SerializerMethodField()

    class Meta:
        model = DesignUpload
        fields = [
            "id",
            "status",
            "review_status",
            "review_reason",
            "width_px",
            "height_px",
            "dpi_estimate",
            "preview_url",
            "created_at",
        ]
        read_only_fields = fields

    def get_preview_url(self, obj) -> str:
        return r2.signed_get_url(obj.r2_key_print) if obj.r2_key_print else ""


class AddToCartSerializer(serializers.Serializer):
    """Input for placing a designed blank into the cart. No price crosses the wire: the
    surcharge is computed server-side from the blank's tiers, and the rights text is the
    server's, snapshotted onto the line."""

    blank_slug = serializers.SlugField()
    design_id = serializers.UUIDField()
    size = serializers.CharField(max_length=16)
    color = serializers.CharField(max_length=40)
    placement_sku = serializers.CharField(max_length=8, default="fr")
    width_inches = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=Decimal("0.5")
    )
    height_inches = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=Decimal("0.5")
    )
    quantity = serializers.IntegerField(min_value=1, max_value=20, default=1)
    rights_accepted = serializers.BooleanField()

    # Optional second placement (the back tab). Present only when the customer printed a back.
    back_design_id = serializers.UUIDField(required=False, allow_null=True)
    back_placement_sku = serializers.CharField(max_length=8, required=False, default="bk")
    back_width_inches = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=Decimal("0.5"), required=False, allow_null=True
    )
    back_height_inches = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=Decimal("0.5"), required=False, allow_null=True
    )


class CustomDesignOrderSerializer(serializers.ModelSerializer):
    """Read shape for a custom line, including Qikink tracking once available."""

    design = DesignUploadSerializer(source="design_upload", read_only=True)

    class Meta:
        model = CustomDesignOrder
        fields = [
            "id",
            "blank_variant",
            "placement_sku",
            "width_inches",
            "height_inches",
            "back_placement_sku",
            "back_width_inches",
            "back_height_inches",
            "quantity",
            "print_surcharge",
            "submit_status",
            "qikink_status",
            "tracking_awb",
            "tracking_link",
            "design",
            "created_at",
        ]
        read_only_fields = fields
