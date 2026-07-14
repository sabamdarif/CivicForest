from django.urls import path

from .views import PaymentVerifyView, RazorpayWebhookView

urlpatterns = [
    path("payments/verify", PaymentVerifyView.as_view(), name="payment-verify"),
    path("payments/webhook/razorpay", RazorpayWebhookView.as_view(), name="razorpay-webhook"),
]
