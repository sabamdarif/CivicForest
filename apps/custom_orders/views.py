"""Custom-design upload API.

The browser never sends image bytes to Django (Vercel's 4.5 MB body cap): it asks for a
presigned URL, PUTs the raw file straight to private R2, then calls ``complete`` to trigger
sanitisation. ``dev_upload`` is a local-only stand-in for R2's PUT endpoint so the whole flow
runs under ``runserver`` (rebuild/03-architecture.md §8)."""

from __future__ import annotations

from django.core.files.storage import storages
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common import r2
from apps.common.throttles import CustomOrderCreateThrottle

from .models import CustomBlank, DesignUpload
from .serializers import (
    AddToCartSerializer,
    CustomDesignOrderSerializer,
    DesignUploadSerializer,
    UploadUrlSerializer,
)
from .services import CustomOrderError, add_design_to_cart
from .uploads import sanitise_upload

_EXT = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}


class DesignUploadUrlView(APIView):
    """Mint a 5-minute presigned PUT into the private designs bucket and record the pending
    upload. Authenticated and throttled: an anonymous or unbounded token would be an open
    door to the bucket (rebuild/02-research.md §1)."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [CustomOrderCreateThrottle]

    def post(self, request):
        form = UploadUrlSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        content_type = form.validated_data["content_type"]
        key = r2.raw_key(_EXT[content_type])
        design = DesignUpload.objects.create(
            user=request.user,
            r2_key_raw=key,
            declared_mime=content_type,
            bytes=form.validated_data["bytes"],
            status=DesignUpload.Status.UPLOADING,
        )
        return Response(
            {
                "design_id": str(design.id),
                "upload_url": r2.presigned_put(key, content_type, expires=300),
                "method": "PUT",
                "headers": {"Content-Type": content_type},
                "expires_in": 300,
            },
            status=status.HTTP_201_CREATED,
        )


class DesignCompleteView(APIView):
    """Called after the browser has PUT the bytes: sanitise the upload inline so the tool can
    show the print-ready preview and its resolution warning. The ``sanitise_designs`` command
    is the backstop for any row left unsanitised."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        design = get_object_or_404(DesignUpload, pk=pk, user=request.user)
        if design.status == DesignUpload.Status.UPLOADING:
            design.status = DesignUpload.Status.UPLOADED
            design.save(update_fields=["status", "updated_at"])
        if design.status == DesignUpload.Status.UPLOADED:
            sanitise_upload(design)
        return Response(DesignUploadSerializer(design).data)


class AddToCartView(APIView):
    """Place a designed blank into the cart. Validates the placement against the blank's own
    print area, then hands off to the service, which computes the surcharge and snapshots the
    rights text (M7.5, M7.11)."""

    permission_classes = [IsAuthenticated]
    throttle_classes = [CustomOrderCreateThrottle]

    def post(self, request):
        form = AddToCartSerializer(data=request.data)
        form.is_valid(raise_exception=True)
        data = form.validated_data

        blank = get_object_or_404(
            CustomBlank.objects.select_related("product"),
            slug=data["blank_slug"],
            is_active=True,
        )
        area = next(
            (
                a
                for a in blank.print_areas.values()
                if a.get("placement_sku") == data["placement_sku"]
            ),
            None,
        )
        if area is None:
            return Response(
                {"error": {"code": "unknown_placement", "message": "Unknown print placement."}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        # Clamp to the printable bounds: the client's size is a hint, never trusted past this.
        width = min(data["width_inches"], area["max_width_in"])
        height = min(data["height_inches"], area["max_height_in"])
        design = get_object_or_404(DesignUpload, id=data["design_id"], user=request.user)

        back = None
        if data.get("back_design_id"):
            back_area = next(
                (
                    a
                    for a in blank.print_areas.values()
                    if a.get("placement_sku") == data["back_placement_sku"]
                ),
                None,
            )
            if back_area is None:
                return Response(
                    {"error": {"code": "unknown_placement", "message": "Unknown back placement."}},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            back = {
                "design": get_object_or_404(
                    DesignUpload, id=data["back_design_id"], user=request.user
                ),
                "placement_sku": data["back_placement_sku"],
                "width_inches": min(data.get("back_width_inches") or 0, back_area["max_width_in"]),
                "height_inches": min(
                    data.get("back_height_inches") or 0, back_area["max_height_in"]
                ),
            }

        try:
            custom = add_design_to_cart(
                request.user,
                blank=blank,
                design=design,
                size=data["size"],
                color=data["color"],
                placement_sku=data["placement_sku"],
                width_inches=width,
                height_inches=height,
                quantity=data["quantity"],
                rights_accepted=data["rights_accepted"],
                back=back,
            )
        except CustomOrderError as exc:
            return Response(
                {"error": {"code": exc.code, "message": exc.message}},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(CustomDesignOrderSerializer(custom).data, status=status.HTTP_201_CREATED)


@csrf_exempt
@require_http_methods(["PUT", "POST"])
def dev_upload(request):
    """Local-only receiver standing in for R2's presigned PUT. Disabled the moment a real
    object store is configured, so it can never accept bytes in production."""
    storage = storages["designs"]
    if getattr(storage, "connection", None) is not None:
        return HttpResponseNotFound()
    key = request.GET.get("key", "")
    if not key:
        return HttpResponseBadRequest("missing key")
    r2.write_bytes(key, request.body)
    return HttpResponse(status=200)
