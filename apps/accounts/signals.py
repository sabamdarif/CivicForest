"""Send the welcome email the first time a customer's address is confirmed.

allauth fires ``email_confirmed`` after the verification link is followed, which is the first
moment a mandatory-verification account is usable, and again on every later email change. The
guard keeps this to the first confirmation: at change time the outgoing address is still present
and verified (it is removed after the signal), so a genuine first verification is the only case
with exactly one verified address. The mail goes through the adapter so it reuses the branded
``account/email/base_message.txt`` every allauth email extends. It carries no discount code: J5's
10% belongs to the newsletter double opt-in in M9, not to a second unconfirmed path here.
"""

from __future__ import annotations

from allauth.account.adapter import get_adapter
from allauth.account.models import EmailAddress
from allauth.account.signals import email_confirmed
from django.dispatch import receiver


@receiver(email_confirmed)
def send_welcome_email(sender, request, email_address, **kwargs):
    if EmailAddress.objects.filter(user_id=email_address.user_id, verified=True).count() == 1:
        get_adapter().send_mail("account/email/welcome", email_address.email, {})
