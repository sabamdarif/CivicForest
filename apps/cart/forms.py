"""Back-office coupon form (M8.9).

A ModelForm over `cart.Coupon` for the back-office CRUD. `used_count` is server-managed (bumped
only by a paid `CouponRedemption`), so it is never editable here; retiring a code is just
`is_active=False`, never a delete, so its redemption history survives.
"""

from __future__ import annotations

from django import forms

from .models import Coupon


class CouponForm(forms.ModelForm):
    class Meta:
        model = Coupon
        fields = [
            "code",
            "discount_type",
            "value",
            "free_shipping",
            "min_order_value",
            "max_uses",
            "per_user_limit",
            "starts_at",
            "expires_at",
            "first_order_only",
            "exclude_sale_items",
            "scope_categories",
            "scope_products",
            "is_active",
        ]

    def clean_code(self):
        return (self.cleaned_data["code"] or "").strip().upper()
