from rest_framework import serializers

from .models import Address, User


class UserSerializer(serializers.ModelSerializer):
    """Read view of the current user. No writable privileged fields exposed."""

    class Meta:
        model = User
        fields = ["id", "email", "first_name", "last_name", "phone", "marketing_opt_in"]
        read_only_fields = ["id", "email"]


class AddressSerializer(serializers.ModelSerializer):
    """Explicit fields — ``user`` is set from the request, never client-supplied,
    to prevent assigning an address to another account (mass assignment / IDOR)."""

    class Meta:
        model = Address
        fields = [
            "id",
            "kind",
            "full_name",
            "phone",
            "line1",
            "line2",
            "city",
            "state",
            "postal_code",
            "country",
            "is_default",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]
