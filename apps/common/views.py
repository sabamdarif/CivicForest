"""Views that belong to no single feature.

The styleguide is the regression surface for every stylesheet, so it sits with the shared
plumbing until M8 task 1 gives the back-office its own app and its `StaffRequiredMixin`.
"""

from django.conf import settings
from django.http import Http404
from django.shortcuts import render


def styleguide(request):
    """Every component in every state, staff only.

    A 404 rather than a redirect, matching ``StaffAdminMiddleware``: a page you may not see
    should not confirm that it exists. DEBUG opens it so a developer reaches it without staff
    credentials; it is only markup with no data behind it, and production forces DEBUG off.
    """
    if not (settings.DEBUG or (request.user.is_authenticated and request.user.is_staff)):
        raise Http404
    return render(request, "backoffice/styleguide.html")
