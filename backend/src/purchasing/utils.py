from decimal import ROUND_HALF_UP, Decimal

TWO_PLACES = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    """Round to 2dp half-up — matches Postgres NUMERIC(x,2) rounding, unlike Decimal's default (half-even)."""
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def escape_like(text: str) -> str:
    """Make `text` safe to embed in a LIKE/ILIKE pattern so `%`, `_` and `\\` match literally —
    pair with `.ilike(..., escape="\\\\")`. Without this, searching "50%" would match everything."""
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
