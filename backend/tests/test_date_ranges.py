"""Plain-assert tests (run: python backend/tests/test_date_ranges.py) for the shared date-range rule and the
party-statement opening balance as of a From date."""
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.dates import InvalidDateRange, validate_date_range  # noqa: E402
from src.parties.service import statement_window  # noqa: E402


def row(i, d, debit, credit):
    return SimpleNamespace(id=i, entry_date=d, account="Accounts Receivable", debit=Decimal(debit), credit=Decimal(credit), reference_type="sales_order", reference_id=i)


ROWS = [row(1, date(2026, 8, 20), 100, 0), row(2, date(2026, 9, 3), 50, 0), row(3, date(2026, 9, 10), 0, 30), row(4, date(2026, 10, 1), 200, 0)]


def test_range_validation():
    validate_date_range(None, None)
    validate_date_range(date(2026, 9, 1), None)
    validate_date_range(None, date(2026, 9, 1))
    validate_date_range(date(2026, 9, 1), date(2026, 9, 1))
    try:
        validate_date_range(date(2026, 9, 2), date(2026, 9, 1))
    except InvalidDateRange as e:
        assert e.status_code == 422
    else:
        raise AssertionError("inverted range accepted")


def test_statement_all_dates_is_the_full_history():
    opening, entries, closing, full = statement_window(Decimal(10), ROWS, None, None)
    assert opening == 10 and len(entries) == 4 and closing == full == Decimal(330)


def test_statement_range_opening_is_balance_before_from():
    opening, entries, closing, full = statement_window(Decimal(10), ROWS, date(2026, 9, 1), date(2026, 9, 30))
    assert opening == Decimal(110)  # 10 + 100 (the 20 Aug row)
    assert [e.id for e in entries] == [2, 3]
    assert entries[0].running_balance == Decimal(160) and entries[1].running_balance == Decimal(130)
    assert closing == Decimal(130) and full == Decimal(330)
    assert opening + sum(e.debit - e.credit for e in entries) == closing


def test_statement_range_without_rows_keeps_the_balance():
    opening, entries, closing, full = statement_window(Decimal(10), ROWS, date(2026, 9, 11), date(2026, 9, 30))
    assert entries == [] and opening == closing == Decimal(130) and full == Decimal(330)


def test_statement_open_ended_ranges():
    _, entries, closing, _ = statement_window(Decimal(10), ROWS, date(2026, 9, 10), None)
    assert [e.id for e in entries] == [3, 4] and closing == Decimal(330)
    opening, entries, closing, _ = statement_window(Decimal(10), ROWS, None, date(2026, 9, 3))
    assert opening == Decimal(10) and [e.id for e in entries] == [1, 2] and closing == Decimal(160)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok  ", name)
