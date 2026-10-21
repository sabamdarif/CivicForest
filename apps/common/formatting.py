"""Money and discount formatting shared by templates and the admin.

Indian digit grouping is the reason this module exists: Django ships no ``en_IN`` locale,
``intcomma`` groups in threes, and ``locale`` needs a locale installed on the host.
"""

from decimal import ROUND_HALF_UP, Decimal


def rupees(value, decimals: int = 2) -> str:
    """``rupees(123456)`` is ``₹1,23,456.00``: three digits, then groups of two."""
    step = Decimal(1).scaleb(-decimals)
    amount = Decimal(str(value or 0)).quantize(step, rounding=ROUND_HALF_UP)
    sign = "-" if amount < 0 else ""
    whole, _, frac = f"{abs(amount):f}".partition(".")

    head, grouped = whole[:-3], whole[-3:]
    groups = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    if groups:
        grouped = ",".join([*groups, grouped])

    return f"{sign}₹{grouped}.{frac}" if decimals else f"{sign}₹{grouped}"


def pct_off(price, mrp) -> int | None:
    """Whole percent off, or None when there is no genuine discount.

    Truncated rather than rounded, so an advertised discount is never larger than the real
    one. Never stored: decision C2 derives it every time.
    """
    if not mrp:
        return None
    price, mrp = Decimal(str(price)), Decimal(str(mrp))
    if mrp <= price:
        return None
    return int((mrp - price) / mrp * 100)
