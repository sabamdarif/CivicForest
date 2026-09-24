"""Storefront pages for the custom line (M7.4, M7.5).

``/customise/`` lists the blanks; ``/customise/<slug>/`` renders the design tool. The tool is
the one documented exception to "works without JavaScript" (it needs a canvas); the page says
so when scripting is unavailable. All money and all validation stay server-side: the page
only hands the tool the blank's configuration to draw with."""

from __future__ import annotations

from django.conf import settings
from django.http import Http404
from django.shortcuts import render

from apps.catalog.models import Size
from apps.common import r2

from .models import CustomBlank, DesignUpload


def customise_landing(request):
    blanks = CustomBlank.objects.filter(is_active=True).select_related("product")
    return render(
        request,
        "customise/landing.html",
        {
            "blanks": blanks,
            "dispatch_days": settings.DISPATCH_DAYS,
            "delivery_days": settings.DELIVERY_DAYS,
        },
    )


def customise_designer(request, slug: str):
    blank = CustomBlank.objects.filter(slug=slug, is_active=True).select_related("product").first()
    if blank is None:
        raise Http404

    variants = list(blank.product.variants.filter(is_active=True))
    size_order = dict(Size.objects.values_list("name", "display_order"))
    sizes = sorted({v.size for v in variants}, key=lambda s: size_order.get(s, 999))
    colours = list({(v.color, v.color_hex) for v in variants})

    saved = []
    if request.user.is_authenticated:
        rows = DesignUpload.objects.filter(
            user=request.user, status=DesignUpload.Status.READY
        ).exclude(review_status=DesignUpload.ReviewStatus.REJECTED)[:12]
        saved = [
            {
                "id": str(d.id),
                "width_px": d.width_px,
                "height_px": d.height_px,
                "preview_url": r2.signed_get_url(d.r2_key_print),
            }
            for d in rows
        ]

    first_image = blank.product.images.first()
    tool_config = {
        "slug": blank.slug,
        "basePrice": str(blank.product.base_price),
        "printAreas": blank.print_areas,
        "surchargeTiers": blank.surcharge_tiers,
        "minDpi": 100,
        "mockupUrl": first_image.image.url if first_image else "",
    }

    return render(
        request,
        "customise/designer.html",
        {
            "blank": blank,
            "sizes": sizes,
            "colours": sorted(colours),
            "saved_designs": saved,
            "rights_text": settings.CUSTOM_RIGHTS_TEXT,
            "tool_config": tool_config,
        },
    )
