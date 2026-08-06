from rest_framework.throttling import UserRateThrottle


class CheckoutMinuteThrottle(UserRateThrottle):
    scope = "checkout"


class CheckoutDayThrottle(UserRateThrottle):
    scope = "checkout_day"


class CustomOrderCreateThrottle(UserRateThrottle):
    scope = "custom_order_create"
