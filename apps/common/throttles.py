"""Named DRF throttle scopes, and the one helper that applies a scope outside DRF.

The rates live in ``REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]``; these classes only name them.
All of them subclass ``UserRateThrottle``, so a signed-in customer is counted by account and a
guest by address.
"""

from rest_framework.throttling import UserRateThrottle


class CheckoutMinuteThrottle(UserRateThrottle):
    scope = "checkout"


class CheckoutDayThrottle(UserRateThrottle):
    scope = "checkout_day"


class CustomOrderCreateThrottle(UserRateThrottle):
    scope = "custom_order_create"


class CouponThrottle(UserRateThrottle):
    """Coupon codes are short and guessable, and a hit is money off. The other cart endpoints
    are self-limiting (ten per line, capped by live stock) and run on the global defaults."""

    scope = "coupon"


def exceeded(request, throttle_class) -> bool:
    """Apply a DRF throttle scope to a plain Django view.

    The storefront's coupon form is where a guesser would actually go, so throttling only the
    JSON endpoint would leave the real door open. ``UserRateThrottle`` never touches the view
    argument, which is what makes it usable from outside DRF.
    """
    return not throttle_class().allow_request(request, None)
