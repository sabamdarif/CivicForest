"""The account area's forms.

ModelForms, because the profile and the address book are plain Django CRUD that posts and
re-renders (P6). Validation that the models do not carry lives here rather than as a migration:
the address book and M6's checkout form should agree about a pincode, and this is the one place
both can use.
"""

from __future__ import annotations

import re

from django import forms

from .models import Address, User

PINCODE = re.compile(r"^[1-9][0-9]{5}$")
PHONE = re.compile(r"^\+?[0-9]{10,15}$")


class ProfileForm(forms.ModelForm):
    """Name, phone and the marketing consent, which is this field's first reader (J9)."""

    class Meta:
        model = User
        fields = ["first_name", "last_name", "phone", "marketing_opt_in"]
        labels = {
            "phone": "Phone number",
            "marketing_opt_in": "Email me new arrivals and offers",
        }
        help_texts = {
            "phone": "Optional here, and asked for again at checkout, because couriers need it.",
            "marketing_opt_in": "Untick at any time. Order updates are sent either way.",
        }

    def clean_phone(self):
        return _clean_phone(self.cleaned_data.get("phone", ""))


class AddressForm(forms.ModelForm):
    """The address book's form.

    `kind` and `country` are not asked: every address here is a shipping address in India, and
    H6 makes billing "same as shipping" by default.
    """

    class Meta:
        model = Address
        fields = [
            "full_name",
            "phone",
            "line1",
            "line2",
            "city",
            "state",
            "postal_code",
            "is_default",
        ]
        labels = {
            "line1": "Address",
            "line2": "Apartment, landmark (optional)",
            "postal_code": "Pincode",
            "is_default": "Use this address by default",
        }

    def clean_phone(self):
        phone = _clean_phone(self.cleaned_data.get("phone", ""))
        if not phone:
            raise forms.ValidationError("A phone number is needed for delivery.")
        return phone

    def clean_postal_code(self):
        pincode = self.cleaned_data.get("postal_code", "").strip()
        if not PINCODE.fullmatch(pincode):
            raise forms.ValidationError("An Indian pincode is six digits and cannot start with 0.")
        return pincode


def _clean_phone(raw: str) -> str:
    """Spaces, dashes and brackets are how people write a number, not part of it."""
    phone = re.sub(r"[\s()-]", "", raw or "")
    if phone and not PHONE.fullmatch(phone):
        raise forms.ValidationError("Enter a phone number of 10 to 15 digits.")
    return phone
