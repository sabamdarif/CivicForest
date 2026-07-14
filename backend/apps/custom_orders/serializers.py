from __future__ import annotations

from rest_framework import serializers

from apps.catalog.models import ProductVariant

from .models import CustomDesignOrder


class CustomDesignCreateSerializer(serializers.Serializer):
    """Upload input. The image itself is validated/re-encoded in the service layer; the
    client-supplied print params are bounded here."""

    design = serializers.FileField()
    variant_id = serializers.UUIDField()
    print_type_id = serializers.IntegerField(min_value=1, max_value=99, default=1)
    placement_sku = serializers.CharField(max_length=8, default="fr")
    width_inches = serializers.DecimalField(max_digits=5, decimal_places=2, default=12)
    height_inches = serializers.DecimalField(max_digits=5, decimal_places=2, default=14)
    quantity = serializers.IntegerField(min_value=1, max_value=20, default=1)

    def validate_variant_id(self, value):
        if not ProductVariant.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Unknown or inactive variant.")
        return value


class CustomDesignOrderSerializer(serializers.ModelSerializer):
    """Read shape — includes Qikink tracking once available. The design file URL is not
    exposed directly; it's served via signed URLs to the print partner only."""

    design_url = serializers.SerializerMethodField()

    class Meta:
        model = CustomDesignOrder
        fields = [
            "id",
            "variant",
            "print_type_id",
            "placement_sku",
            "width_inches",
            "height_inches",
            "quantity",
            "review_status",
            "submit_status",
            "qikink_status",
            "tracking_awb",
            "tracking_link",
            "design_url",
            "created_at",
        ]
        read_only_fields = fields

    def get_design_url(self, obj) -> str | None:
        if not obj.design_file:
            return None
        request = self.context.get("request")
        url = obj.design_file.url
        return request.build_absolute_uri(url) if request else url
