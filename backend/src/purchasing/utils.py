from decimal import ROUND_HALF_UP, Decimal

TWO_PLACES = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    """Round to 2dp half-up — matches Postgres NUMERIC(x,2) rounding, unlike Decimal's default (half-even)."""
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
