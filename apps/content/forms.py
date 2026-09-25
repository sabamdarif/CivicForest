"""Back-office content forms (M8.12, O10): the announcement bar and the home page sections.

ModelForms over the existing content models. Image uploads are held to the same content sniff the
product gallery uses, so a disguised file cannot be stored. `Page` and `FaqEntry` are not here:
their models land with M9, and their editors land with them.
"""

from __future__ import annotations

from django import forms

from apps.custom_orders.uploads import UploadError, validate_product_image

from .models import AnnouncementBar, HomeSection


def _validate_image_field(form: forms.ModelForm, field: str):
    """Run the upload sniff on a freshly uploaded image; leave an untouched existing file alone."""
    uploaded = form.files.get(field)
    if uploaded is None:
        return form.cleaned_data.get(field)
    try:
        validate_product_image(uploaded)
    except UploadError as exc:
        raise forms.ValidationError(exc.message) from exc
    return uploaded


class AnnouncementBarForm(forms.ModelForm):
    class Meta:
        model = AnnouncementBar
        fields = ["text", "url", "is_active", "starts_at", "ends_at"]


class HomeSectionForm(forms.ModelForm):
    class Meta:
        model = HomeSection
        fields = [
            "kind",
            "eyebrow",
            "title",
            "subtitle",
            "image",
            "target",
            "cta_label",
            "display_order",
            "is_active",
        ]

    def clean_image(self):
        return _validate_image_field(self, "image")
