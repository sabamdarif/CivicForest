"""Account API and customer-owned storefront pages."""

import json

from allauth.account.decorators import reauthentication_required
from allauth.account.internal.flows.reauthentication import did_recently_authenticate
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.generics import RetrieveUpdateAPIView
from rest_framework.permissions import IsAuthenticated

from .forms import AddressForm, ProfileForm
from .models import Address, DataRequest
from .serializers import AddressSerializer, UserSerializer
from .services import (
    dashboard_summary,
    delete_address,
    export_payload,
    request_erasure,
    save_address,
    security_overview,
    set_default_address,
)


class CurrentUserView(RetrieveUpdateAPIView):
    """GET/PATCH the authenticated user's own profile."""

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class AddressViewSet(viewsets.ModelViewSet):
    """CRUD for the caller's addresses, with recent authentication for API writes."""

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
                    "oauth_reauthentication_required" if oauth_only else "reauthentication_required"
                ),
            )

    def perform_create(self, serializer):
        self._require_recent_login()
        serializer.instance = save_address(self.request.user, Address(**serializer.validated_data))

    def perform_update(self, serializer):
        self._require_recent_login()
        for name, value in serializer.validated_data.items():
            setattr(serializer.instance, name, value)
        save_address(self.request.user, serializer.instance)

    def perform_destroy(self, instance):
        self._require_recent_login()
        delete_address(self.request.user, instance)


@login_required
def dashboard(request):
    return render(request, "account/dashboard.html", dashboard_summary(request.user))


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your profile has been updated.")
        return redirect("account-profile")
    return render(request, "account/profile.html", {"form": form})


@login_required
def addresses(request):
    return render(
        request,
        "account/addresses.html",
        {"addresses": Address.objects.filter(user=request.user)},
    )


@login_required
def address_add(request):
    form = AddressForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        address = form.save(commit=False)
        save_address(request.user, address)
        messages.success(request, "Your address has been saved.")
        return redirect("account-addresses")
    return render(request, "account/address_form.html", {"form": form, "editing": False})


@login_required
def address_edit(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    form = AddressForm(request.POST or None, instance=address)
    if request.method == "POST" and form.is_valid():
        save_address(request.user, form.save(commit=False))
        messages.success(request, "Your address has been updated.")
        return redirect("account-addresses")
    return render(request, "account/address_form.html", {"form": form, "editing": True})


@login_required
@require_POST
def address_default(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    set_default_address(request.user, address)
    messages.success(request, "Your default address has been updated.")
    return redirect("account-addresses")


@login_required
def address_delete(request, pk):
    address = get_object_or_404(Address, pk=pk, user=request.user)
    if request.method == "POST":
        delete_address(request.user, address)
        messages.success(request, "Your address has been deleted.")
        return redirect("account-addresses")
    return render(request, "account/address_confirm_delete.html", {"address": address})


@login_required
def security(request):
    return render(request, "account/security.html", security_overview(request.user))


@login_required
def data(request):
    open_erasure = DataRequest.objects.filter(
        user=request.user,
        kind=DataRequest.Kind.ERASURE,
        status=DataRequest.Status.OPEN,
    ).first()
    return render(request, "account/data.html", {"open_erasure": open_erasure})


@login_required
@reauthentication_required
@require_POST
def data_export(request):
    payload = export_payload(request.user)
    now = timezone.now()
    DataRequest.objects.create(
        user=request.user,
        kind=DataRequest.Kind.EXPORT,
        status=DataRequest.Status.DONE,
        handled_at=now,
    )
    response = HttpResponse(
        json.dumps(payload, ensure_ascii=False, indent=2),
        content_type="application/json",
    )
    response["Content-Disposition"] = f'attachment; filename="civicforest-data-{now.date()}.json"'
    response["Cache-Control"] = "private, no-store"
    return response


@login_required
@reauthentication_required
@require_POST
def data_erasure(request):
    _, created = request_erasure(request.user)
    if created:
        messages.success(request, "Your erasure request has been submitted for review.")
    else:
        messages.info(request, "Your erasure request is already awaiting review.")
    return redirect("account-data")
