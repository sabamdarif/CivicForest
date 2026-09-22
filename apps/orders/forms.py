"""The checkout form.

A plain Django form so checkout posts and re-renders without JavaScript (the hard "works
without JS" requirement). It collects the contact phone, a shipping address (either a saved
one the customer picks, or a new one they type), the save-address flag, and the terms
acknowledgement, which is unticked by default and required to submit (no dark patterns).
Address validation reuses the accounts validators so the address book and checkout agree.
"""

from __future__ import annotations

from django import forms

from apps.accounts.forms import PINCODE, _clean_phone


class CheckoutForm(forms.Form):
    phone = forms.CharField(max_length=20, label="Phone number")

    # Populated per-user in __init__. Empty value = "a new address", so the fields below apply.
    saved_address = forms.ChoiceField(required=False, label="Saved addresses")

    full_name = forms.CharField(max_length=120, required=False, label="Full name")
    line1 = forms.CharField(max_length=255, required=False, label="Address")
    line2 = forms.CharField(max_length=255, required=False, label="Apartment, landmark (optional)")
    city = forms.CharField(max_length=100, required=False, label="City")
    state = forms.CharField(max_length=100, required=False, label="State")
    postal_code = forms.CharField(max_length=16, required=False, label="Pincode")

    save_address = forms.BooleanField(required=False, label="Save this address to my account")
    accept_terms = forms.BooleanField(
        required=True, label="", error_messages={"required": "You must accept the terms."}
    )

    def __init__(self, *args, addresses=None, **kwargs):
        super().__init__(*args, **kwargs)
        choices = [("", "Use a new address")]
        choices += [(str(a.id), self._label(a)) for a in addresses or []]
        self.fields["saved_address"].choices = choices

    @staticmethod
    def _label(address) -> str:
        return f"{address.full_name}, {address.line1}, {address.city} {address.postal_code}"

    def clean_phone(self):
        phone = _clean_phone(self.cleaned_data.get("phone", ""))
        if not phone:
            raise forms.ValidationError("A phone number is needed for delivery.")
        return phone

    def clean(self):
        cleaned = super().clean()
        # A saved address is validated already; only a typed new address needs checking.
        if cleaned.get("saved_address"):
            return cleaned
        required = ["full_name", "line1", "city", "state", "postal_code"]
        for field in required:
            if not cleaned.get(field):
                self.add_error(field, "This field is required.")
        pincode = (cleaned.get("postal_code") or "").strip()
        if pincode and not PINCODE.fullmatch(pincode):
            self.add_error(
                "postal_code", "An Indian pincode is six digits and cannot start with 0."
            )
        return cleaned
