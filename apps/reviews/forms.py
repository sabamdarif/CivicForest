"""The customer's review form: rating, optional title and body, optional fit feedback.

A ModelForm over the four customer-set fields only. Product, user, order line and moderation
status are set by the service from the proven purchase, never from the form, so a posted product
or status is ignored.
"""

from __future__ import annotations

from django import forms

from .models import Review

_RATING_CHOICES = [
    (5, "5 - Excellent"),
    (4, "4 - Good"),
    (3, "3 - Okay"),
    (2, "2 - Poor"),
    (1, "1 - Terrible"),
]


class ReviewForm(forms.ModelForm):
    rating = forms.TypedChoiceField(choices=_RATING_CHOICES, coerce=int, empty_value=None)

    class Meta:
        model = Review
        fields = ["rating", "fit_feedback", "title", "body"]
        widgets = {
            "title": forms.TextInput(attrs={"maxlength": 120}),
            "body": forms.Textarea(attrs={"rows": 5}),
        }
        labels = {"body": "Your review", "fit_feedback": "How does it fit?"}
