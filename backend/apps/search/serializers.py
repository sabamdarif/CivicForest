from rest_framework import serializers


class SuggestionHitSerializer(serializers.Serializer):
    """Minimal dropdown payload — name, slug, thumbnail, price, category. Nothing
    heavier: the full product payload is a separate, deliberate request (plan.md §7)."""

    id = serializers.CharField()
    name = serializers.CharField()
    slug = serializers.CharField()
    category = serializers.CharField(allow_null=True)
    category_slug = serializers.CharField(allow_null=True, required=False)
    price_from = serializers.FloatField(allow_null=True)
    thumbnail = serializers.CharField(allow_null=True)
