"""One rendering of a bound form field's widget, shared by both template engines.

The account pages are Jinja2 and allauth's are the Django Template Language, but both put Django
forms on the screen, and both need the same three things on the control: the site's class, and the
`aria-describedby` and `aria-invalid` that tell a screen reader why a value was rejected (L6). It
lives here rather than in a templatetags module because `config/jinja2.py` registers it too.
"""

from __future__ import annotations


def control(field, css: str = "field__control") -> str:
    """Render one bound field's widget wearing the site's classes and its error wiring."""
    attrs = {"class": css}
    described = []
    if field.help_text:
        described.append(f"{field.auto_id}-hint")
    if field.errors:
        described.append(f"{field.auto_id}-error")
        attrs["aria-invalid"] = "true"
    if described:
        attrs["aria-describedby"] = " ".join(described)
    return field.as_widget(attrs=attrs)
