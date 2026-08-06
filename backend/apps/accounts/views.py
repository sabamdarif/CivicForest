# ponytail: did_recently_authenticate lives in allauth's internal flows module —
# it's the same primitive allauth uses for its own MFA "sudo mode" checks. Pin
# review on allauth upgrades; switch to a public API if one appears.
from allauth.account.internal.flows.reauthentication import did_recently_authenticate
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated

from .models import Address
from .serializers import AddressSerializer, UserSerializer


class CurrentUserView(RetrieveUpdateAPIView):
    """GET/PATCH the authenticated user's own profile."""

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class AddressViewSet(viewsets.ModelViewSet):
    """CRUD for the current user's addresses. Querysets are always scoped to
    ``request.user`` so one account can never read or edit another's (plan.md §5).

    Changing or deleting a saved address requires a recent login (allauth's
    reauthentication window): the client gets a 403 ``reauthentication_required``,
    prompts for the password, POSTs /_allauth/.../auth/reauthenticate, and retries.
    """

    serializer_class = AddressSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def _require_recent_login(self):
        if not did_recently_authenticate(self.request):
            oauth_only = not self.request.user.has_usable_password()
            raise PermissionDenied(
                detail=(
                    "Please sign in with your identity provider again to change a saved address."
                    if oauth_only
                    else "Please confirm your password to change a saved address."
                ),
                code=(
                    "oauth_reauthentication_required"
                    if oauth_only
                    else "reauthentication_required"
                ),
            )

    def _sync_default(self, address):
        # Only one default address per user.
        if address.is_default:
            Address.objects.filter(user=self.request.user, is_default=True).exclude(
                pk=address.pk
            ).update(is_default=False)

    def perform_create(self, serializer):
        self._require_recent_login()
        self._sync_default(serializer.save(user=self.request.user))

    def perform_update(self, serializer):
        self._require_recent_login()
        self._sync_default(serializer.save())

    def perform_destroy(self, instance):
        self._require_recent_login()
        instance.delete()
