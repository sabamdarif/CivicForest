"""Jinja2 environment for every page this project renders.

Jinja2 has no context processors, so anything a template needs globally is registered
here. Django's backend already injects ``request``, ``csrf_input`` and ``csrf_token``
when a template is rendered with a request, so those are deliberately absent.
"""

from django.contrib.messages import get_messages
from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from jinja2 import Environment, FileSystemBytecodeCache

from apps.common.formatting import pct_off, rupees


def announcement():
    """The live announcement bar, or None. Imported inside the call because the app
    registry is not ready when the template environment is built."""
    from apps.content.services import current_announcement

    return current_announcement()


def nav_categories():
    """Top-level categories for the SHOP dropdown (D13), which the header renders on every
    page. Same deferred import as ``announcement``, and the same one indexed query."""
    from apps.catalog.services import nav_categories as fetch

    return fetch()


def srcset(image):
    """The generated widths of a ProductImage as a srcset value (P8). Imported inside the
    call for the same reason as ``announcement``."""
    from apps.catalog.services import srcset as build

    return build(image)


def card_data(product):
    """A product mapped onto the ``product_card()`` macro's arguments."""
    from apps.catalog.services import card_data as build

    return build(product)


def environment(**options):
    # /tmp is the only writable path on Vercel and it survives inside a warm instance,
    # so compiled templates are cached there instead of recompiled per request.
    options.setdefault("bytecode_cache", FileSystemBytecodeCache())
    env = Environment(**options)
    env.globals.update(
        {
            "static": static,
            "url": reverse,
            "now": timezone.localtime,
            "announcement": announcement,
            "nav_categories": nav_categories,
            # Jinja2 has no context processors, so a template asks for the request's messages
            # by hand. A form that posts and redirects is how feedback reaches a page with no
            # JavaScript (P6), so every such page renders these.
            "get_messages": get_messages,
        }
    )
    env.filters.update(
        {
            "rupees": rupees,
            "pct_off": pct_off,
            "srcset": srcset,
            "card_data": card_data,
        }
    )
    return env
