"""Jinja2 environment for every page this project renders.

Jinja2 has no context processors, so anything a template needs globally is registered
here. Django's backend already injects ``request``, ``csrf_input`` and ``csrf_token``
when a template is rendered with a request, so those are deliberately absent.
"""

from django.templatetags.static import static
from django.urls import reverse
from django.utils import timezone
from jinja2 import Environment, FileSystemBytecodeCache

from apps.common.formatting import pct_off, rupees


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
        }
    )
    env.filters.update(
        {
            "rupees": rupees,
            "pct_off": pct_off,
        }
    )
    return env
