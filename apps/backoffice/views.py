"""Back-office pages.

Views are thin: they call `apps.backoffice.services` (or another app's services) and render a
`backoffice/*` template. No business logic lives here. `styleguide` moved here from
`apps.common.views` when M8.1 gave the back-office its own app; it stays staff-only markup with
no data behind it, so its gate is `is_staff`/DEBUG rather than the full MFA mixin.
"""

from django.conf import settings
from django.http import Http404
from django.shortcuts import render
from django.views.generic import TemplateView

from .mixins import StaffRequiredMixin


class DashboardView(StaffRequiredMixin, TemplateView):
    """The back-office landing. M8.3 fills the O1 tiles and charts."""

    template_name = "backoffice/dashboard.html"


def styleguide(request):
    """Every component in every state, staff only.

    A 404 rather than a redirect, matching `StaffAdminMiddleware`: a page you may not see should
    not confirm that it exists. DEBUG opens it so a developer reaches it without staff
    credentials; it is only markup with no data behind it, and production forces DEBUG off.
    """
    if not (settings.DEBUG or (request.user.is_authenticated and request.user.is_staff)):
        raise Http404
    return render(request, "backoffice/styleguide.html")
