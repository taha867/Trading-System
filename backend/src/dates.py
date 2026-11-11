"""One rule for "from / to" date filters, shared by every list and report endpoint."""
from datetime import date

from src.exceptions import AppException


class InvalidDateRange(AppException):
    status_code = 422
    detail = "date_from must be on or before date_to"


def validate_date_range(date_from: date | None, date_to: date | None, error: type[AppException] = InvalidDateRange) -> None:
    """Both ends are inclusive and optional; when both are given the start cannot be after the end."""
    if date_from is not None and date_to is not None and date_from > date_to:
        raise error("date_from must be on or before date_to")
