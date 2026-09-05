"""What a Django Template Language page borrows from the site's Jinja2 presentation.

allauth ships DTL templates and every page this project owns is Jinja2, so rather than a
second copy of the chrome and of the form markup there are two helpers here: one tag that
renders a Jinja2 partial, and one filter that gives a Django widget the site's control
classes and its error wiring (rebuild/03-architecture.md §3).
"""

from django import template
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

register = template.Library()


@register.simple_tag(takes_context=True)
def jinja_partial(context, template_name, **extra):
    """Render one Jinja2 template and return its markup.

    Passing the request is what puts ``csrf_input`` and ``csrf_token`` in the partial's
    context, which the footer's newsletter form needs. The Jinja2 environment autoescapes,
    so the result is already safe and only needs marking as such.
    """
    return mark_safe(
        render_to_string(template_name, extra, request=context.get("request"), using="jinja2")
    )


@register.filter
def control(field, css="field__control"):
    """One bound form field's widget, wearing the site's classes.

    Widget attributes are the only place a class can be added to a form allauth owns, and
    the same call is what associates the hint and the error text with the control, so a
    screen reader hears why a value was rejected (L6, WCAG 2.2 AA).
    """
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
