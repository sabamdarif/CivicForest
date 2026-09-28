"""The home page and the static content surface (M9.5).

The home view composes: which bands appear and in what order is content (`HomeSection`), and what
goes inside them is catalogue. Neither service calls the other. `page` renders a published `Page`
by slug (a draft or missing slug is a 404); `faq` renders the active FAQ entries as an accordion.
"""

from django.conf import settings
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme

from apps.catalog import services as catalog
from apps.common import seo
from apps.common.throttles import ContactThrottle, NewsletterThrottle, exceeded

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


def _back(request):
    """Redirect to the page the subscribe form was posted from, guarding against an open redirect
    to another host. Anything off-site falls back to home."""
    ref = request.META.get("HTTP_REFERER", "")
    if ref and url_has_allowed_host_and_scheme(
        ref, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return redirect(ref)
    return redirect("home")


def _newsletter_result(request, title: str, body: str, status: int = 200):
    return render(
        request, "content/newsletter_result.html", {"heading": title, "body": body}, status=status
    )


def newsletter_subscribe(request):
    """Footer subscribe (J5): a plain POST that mails a confirm link. The reply is the same for a
    new, known or invalid address, so the endpoint cannot be used to learn who is subscribed, and
    no code is issued until the address is confirmed."""
    if request.method != "POST":
        return redirect("home")
    if exceeded(request, NewsletterThrottle):
        messages.error(request, "Too many requests just now. Please wait a minute and retry.")
        return _back(request)
    email = (request.POST.get("email") or "").strip()
    try:
        validate_email(email)
        services.subscribe(email, source="footer")
    except ValidationError:
        pass
    messages.success(request, "Almost there: check your inbox to confirm your subscription.")
    return _back(request)


def newsletter_confirm(request, token):
    """Open the signed confirm link (J5). First confirmation mints and mails the welcome code."""
    if services.confirm_subscription(token) is None:
        return _newsletter_result(
            request,
            "This link is invalid or has expired",
            "Confirmation links last seven days. Please subscribe again from any page footer.",
            status=400,
        )
    return _newsletter_result(
        request,
        "You're subscribed",
        "Thanks for confirming. Your 10% welcome code is on its way to your inbox.",
    )


def newsletter_unsubscribe(request, token):
    """One-click unsubscribe from the signed link in every newsletter (J5), no login."""
    if services.unsubscribe(token) is None:
        return _newsletter_result(
            request,
            "This link is not recognised",
            "If you keep receiving newsletters, contact support and we'll remove you.",
            status=400,
        )
    return _newsletter_result(
        request,
        "You've been unsubscribed",
        "You won't receive any more newsletters. You can resubscribe any time.",
    )
