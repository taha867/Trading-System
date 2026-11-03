import calendar
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from src.reporting.constants import MAX_REPORT_RANGE_DAYS
from src.reporting.exceptions import InvalidReportPeriod

TWO_PLACES = Decimal("0.01")


def money(value: Decimal) -> Decimal:
    """Round to 2dp half-up — matches Postgres NUMERIC(x,2) rounding, unlike Decimal's default (half-even).
    Also used to round quantity sums in this module: StockLot.qty_remaining and SalesOrderLine.qty are
    both NUMERIC(10,2) — the same scale as the money columns this helper was written for."""
    return value.quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def validate_period(date_from: date, date_to: date) -> None:
    if date_from > date_to:
        raise InvalidReportPeriod("date_from must be on or before date_to")
    if (date_to - date_from).days + 1 > MAX_REPORT_RANGE_DAYS:
        raise InvalidReportPeriod(f"Report period cannot exceed {MAX_REPORT_RANGE_DAYS} days")


def previous_period(date_from: date, date_to: date) -> tuple[date, date]:
    """The period to compare against. A full calendar month compares with the previous full calendar
    month (so October is compared with September's 30 days, not with the 31 days before October 1st);
    any other range compares with the same number of days directly before it."""
    last_day = calendar.monthrange(date_from.year, date_from.month)[1]
    if date_from.day == 1 and date_to == date_from.replace(day=last_day):
        prev_to = date_from - timedelta(days=1)
        return prev_to.replace(day=1), prev_to

    length = (date_to - date_from).days + 1
    prev_to = date_from - timedelta(days=1)
    return prev_to - timedelta(days=length - 1), prev_to
