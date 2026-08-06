"""Custom-design upload API.

The browser uploads the raw image here (never to Qikink — credentials stay server-side).
We content-validate + re-encode it, store it privately, and create a
``CustomDesignOrder`` in ``pending_payment``. Files that fail checks are stored but
``flagged`` so they can be eyeballed before ever reaching Qikink (plan.md §8)."""

from __future__ import annotations

from rest_framework import mixins, status, viewsets
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.catalog.models import ProductVariant
from apps.common.throttles import CustomOrderCreateThrottle

from .models import CustomDesignOrder
from .serializers import CustomDesignCreateSerializer, CustomDesignOrderSerializer
from .uploads import UploadError, validate_and_reencode


class CustomDesignViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Create (upload) and read the caller's own custom-design orders."""

    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    serializer_class = CustomDesignOrderSerializer

    def get_queryset(self):
        return CustomDesignOrder.objects.filter(user=self.request.user).select_related("variant")

    def get_throttles(self):
        if self.action == "create":
            return [CustomOrderCreateThrottle()]
        return super().get_throttles()

    def create(self, request, *args, **kwargs):
        form = CustomDesignCreateSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data

        try:
            sanitised = validate_and_reencode(data["design"])
        except UploadError as exc:
            return Response(
                {"error": {"code": exc.code, "message": exc.message, "details": {}}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        variant = ProductVariant.objects.get(id=data["variant_id"])
        custom = CustomDesignOrder(
            user=request.user,
            variant=variant,
            print_type_id=data["print_type_id"],
            placement_sku=data["placement_sku"],
            width_inches=data["width_inches"],
            height_inches=data["height_inches"],
            quantity=data["quantity"],
        )
        custom.design_file.save(sanitised.name, sanitised, save=False)
        custom.save()

        return Response(
            CustomDesignOrderSerializer(custom, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )
