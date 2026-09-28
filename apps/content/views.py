"""The home page and the static content surface (M9.5).

The home view composes: which bands appear and in what order is content (`HomeSection`), and what
goes inside them is catalogue. Neither service calls the other. `page` renders a published `Page`
by slug (a draft or missing slug is a 404); `faq` renders the active FAQ entries as an accordion.
"""

from django.conf import settings
from django.contrib import messages
from django.http import Http404
from django.shortcuts import redirect, render

from apps.catalog import services as catalog
from apps.common import seo
from apps.common.throttles import ContactThrottle, exceeded

from . import services
from .forms import ContactForm


def home(request):
    return render(
        request,
        "home.html",
        {
            "sections": services.home_sections(),
            # Four tiles, as the reference shows. Which four is display_order's job, and the
            # full set is on /shop/ behind the category facet.
            "categories": catalog.nav_categories()[:4],
            "just_landed": catalog.new_arrivals(4),
            "structured_data": [seo.organisation(request), seo.website(request)],
        },
    )


def page(request, slug):
    """A published static page (L2). A draft or unknown slug is a 404, never a blank shell."""
    content_page = services.get_published_page(slug)
    if content_page is None:
        raise Http404
    trail = [("Home", "/")]
    return render(
        request,
        "content/page.html",
        {
            "page": content_page,
            "trail": trail,
            "current": content_page.title,
            "structured_data": [seo.breadcrumb_list(request, trail, content_page.title)],
        },
    )


def faq(request):
    """The FAQ accordion with FAQPage markup (N3), grouped by category."""
    groups = services.faq_grouped()
    return render(
        request,
        "content/faq.html",
        {"faq_groups": groups, "structured_data": [seo.faq_page(request, groups)]},
    )


def contact(request):
    """The contact form (N1): honeypot plus rate limit, no CAPTCHA, works without JavaScript. A
    tripped honeypot returns success so a bot learns nothing; the message is stored and the support
    inbox notified only on a clean, in-limit, valid submission."""
    form = ContactForm(request.POST or None)
    if request.method == "POST":
        if request.POST.get("website"):  # honeypot: a human never fills this
            messages.success(request, "Thanks for your message. We'll be in touch soon.")
            return redirect("contact")
        if exceeded(request, ContactThrottle):
            messages.error(request, "Too many messages just now. Please wait a minute and retry.")
        elif form.is_valid():
            services.record_contact_message(**form.cleaned_data)
            messages.success(request, "Thanks for your message. We'll be in touch soon.")
            return redirect("contact")
    return render(request, "content/contact.html", {"form": form})


def grievance(request):
    """The Grievance Redressal page (L1), legally required. Driven by settings so the named officer
    and contact details are always present and cannot be blanked by a content edit (research §5)."""
    trail = [("Home", "/")]
    return render(
        request,
        "content/grievance.html",
        {
            "officer": {
                "name": settings.GRIEVANCE_OFFICER_NAME,
                "email": settings.GRIEVANCE_EMAIL,
                "phone": settings.GRIEVANCE_PHONE,
                "address": settings.GRIEVANCE_ADDRESS,
                "response_hours": settings.GRIEVANCE_RESPONSE_HOURS,
            },
            "seller": {"name": settings.SELLER_LEGAL_NAME, "address": settings.SELLER_ADDRESS},
            "trail": trail,
            "current": "Grievance Redressal",
            "structured_data": [seo.breadcrumb_list(request, trail, "Grievance Redressal")],
        },
    )
