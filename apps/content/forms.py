"""Back-office content forms (M8.12, O10): the announcement bar and the home page sections.

ModelForms over the existing content models. Image uploads are held to the same content sniff the
product gallery uses, so a disguised file cannot be stored. `Page` and `FaqEntry` are not here:
their models land with M9, and their editors land with them.
"""

from __future__ import annotations

from django import forms

from apps.custom_orders.uploads import UploadError, validate_product_image

from .models import AnnouncementBar, ContactMessage, FaqEntry, HomeSection, Page


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


class PageForm(forms.ModelForm):
    class Meta:
        model = Page
        fields = ["slug", "title", "body", "meta_title", "meta_description", "is_published"]
        widgets = {"body": forms.Textarea(attrs={"rows": 16})}


class FaqEntryForm(forms.ModelForm):
    class Meta:
        model = FaqEntry
        fields = ["question", "answer", "category", "display_order", "is_active"]
        widgets = {"answer": forms.Textarea(attrs={"rows": 6})}


class ContactForm(forms.ModelForm):
    """The public contact form (N1). The honeypot is a separate hidden field checked in the view,
    not here, so a tripped honeypot looks like success to a bot rather than a validation error."""

    class Meta:
        model = ContactMessage
        fields = ["name", "email", "order_number", "subject", "message"]
        labels = {"order_number": "Order number (optional)"}
        widgets = {"message": forms.Textarea(attrs={"rows": 6})}
