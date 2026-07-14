"""Order + checkout API.

- ``GET /orders`` / ``GET /orders/<order_number>`` — the caller's own orders only,
  looked up by the non-guessable public order number (ownership-scoped, no IDOR).
- ``POST /checkout`` — snapshot the cart into an order and create a Razorpay order,
  computing the amount server-side. Returns what the browser needs to open Razorpay's
  hosted checkout."""

from __future__ import annotations

from django.conf import settings
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.cart import services as cart_services
from apps.payments import gateway as payment_gateway
from apps.payments import services as payment_services

from . import services
from .models import Order
from .serializers import CheckoutSerializer, OrderSerializer


class OrderViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Read-only list/detail of the authenticated user's orders."""

    serializer_class = OrderSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = "order_number"

    def get_queryset(self):
        return (
            Order.objects.filter(user=self.request.user)
            .prefetch_related("items")
            .order_by("-created_at")
        )


class CheckoutView(APIView):
    """Create an order from the current cart and open a Razorpay order for it."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CheckoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        shipping = serializer.validated_data["shipping_address"]

        cart = cart_services.get_or_create_cart(request)
        try:
            order = services.create_order_from_cart(request.user, cart, shipping)
        except services.OrderError as exc:
            return Response(
                {"error": {"code": exc.code, "message": exc.message, "details": {}}},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if serializer.validated_data.get("save_address"):
            self._save_address(request.user, shipping)

        try:
            payment = payment_services.create_gateway_order(order)
        except payment_gateway.PaymentError as exc:
            # Roll the order back to a cancellable state so it isn't stuck pending.
            services.transition(order, Order.Status.CANCELLED)
            return Response(
                {"error": {"code": exc.code, "message": exc.message, "details": {}}},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "order_number": order.order_number,
                "razorpay_order_id": payment.gateway_order_id,
                "razorpay_key_id": settings.RAZORPAY_KEY_ID,
                "amount": str(order.total),
                "amount_paise": payment_gateway.to_paise(order.total),
                "currency": order.currency,
            },
            status=status.HTTP_201_CREATED,
        )

    @staticmethod
    def _save_address(user, shipping):
        from apps.accounts.models import Address

        Address.objects.get_or_create(
            user=user,
            line1=shipping["line1"],
            postal_code=shipping["postal_code"],
            defaults={
                "full_name": shipping["full_name"],
                "phone": shipping["phone"],
                "line2": shipping.get("line2", ""),
                "city": shipping["city"],
                "state": shipping["state"],
                "country": shipping.get("country", "IN"),
            },
        )
