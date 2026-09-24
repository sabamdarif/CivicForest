"""Access control shared by every back-office view.

`StaffRequiredMixin` is the outer gate: `is_staff` plus a confirmed TOTP step in this session,
the same rule `StaffAdminMiddleware` enforces on the admin path (`session_completed_mfa`). Set
`permission_required` on a view to add a Django permission check on top. Every failure raises
`Http404`, never a redirect, so a page a user may not see never confirms that it exists.
"""

from __future__ import annotations

from django.http import Http404

from apps.common.middleware import session_completed_mfa


class StaffRequiredMixin:
    # A dotted permission string or an iterable of them; None means the staff gate alone.
    permission_required: str | tuple[str, ...] | None = None

    def dispatch(self, request, *args, **kwargs):
        user = getattr(request, "user", None)
        if not (
            user and user.is_authenticated and user.is_staff and session_completed_mfa(request)
        ):
            raise Http404
        if self.permission_required and not user.has_perms(self._required_perms()):
            raise Http404
        return super().dispatch(request, *args, **kwargs)

    def _required_perms(self) -> tuple[str, ...]:
        perms = self.permission_required
        return (perms,) if isinstance(perms, str) else tuple(perms)
