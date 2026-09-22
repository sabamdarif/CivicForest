"""What a Django Template Language page borrows from the site's Jinja2 presentation.

allauth ships DTL templates and every page this project owns is Jinja2, so rather than a second
copy of the chrome there is one tag here that renders a Jinja2 partial. The `control` filter is the
same callable `config/jinja2.py` registers, so a form field looks the same whichever engine drew it
(rebuild/03-architecture.md §3).
"""

from django import template
from django.template.loader import render_to_string
from django.utils.safestring import mark_safe

from apps.common.forms import control as render_control

register = template.Library()


@register.simple_tag(takes_context=True)
def jinja_partial(context, template_name, **extra):
    """Render one Jinja2 template and return its markup.

    Passing the request is what puts ``csrf_input`` and ``csrf_token`` in the partial's context,
    which the footer's newsletter form needs. The Jinja2 environment autoescapes, so the result is
    already safe and only needs marking as such.
    """
    return mark_safe(
        render_to_string(template_name, extra, request=context.get("request"), using="jinja2")
    )


register.filter("control", render_control)
