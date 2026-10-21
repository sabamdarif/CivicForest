"""Indian digit grouping and the derived discount percentage.

Both are pure functions with no database, so this is where the arithmetic edge cases live:
the group boundary at ₹1,000 and ₹1,00,000, paise rounding, and a discount that is not
really a discount.
"""

from decimal import Decimal

import pytest

from apps.common.formatting import pct_off, rupees


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, "₹0.00"),
        (79, "₹79.00"),
        (999, "₹999.00"),
        (1000, "₹1,000.00"),
        (99999, "₹99,999.00"),
        (100000, "₹1,00,000.00"),
        (12345678, "₹1,23,45,678.00"),
        (Decimal("2847.5"), "₹2,847.50"),
        (Decimal("1274.005"), "₹1,274.01"),
        (Decimal("-150"), "-₹150.00"),
    ],
)
def test_rupees_groups_the_indian_way(value, expected):
    assert rupees(value) == expected


def test_rupees_without_paise():
    assert rupees(Decimal("123456.78"), decimals=0) == "₹1,23,457"


@pytest.mark.parametrize(
    ("price", "mrp", "expected"),
    [
        (1274, 1499, 15),
        (799, 999, 20),
        (999, 999, None),
        (999, 799, None),
        (799, None, None),
        (Decimal("1199.00"), Decimal("1399.00"), 14),
    ],
)
def test_pct_off_never_overstates_the_discount(price, mrp, expected):
    assert pct_off(price, mrp) == expected
