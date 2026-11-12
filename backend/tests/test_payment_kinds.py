"""Plain-assert tests (run: python backend/tests/test_payment_kinds.py) for the payment kind rule used by the Payments list."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.payments.constants import PAYMENT_KINDS, classify_payment  # noqa: E402


def test_expense_wins_whatever_else():
    assert classify_payment("out", None, "expense") == "expense"
    assert classify_payment("out", 5, "expense") == "expense"


def test_party_rows_follow_the_direction():
    assert classify_payment("in", 7, None) == "customer_receipt"
    assert classify_payment("in", 7, "sales_order") == "customer_receipt"
    assert classify_payment("out", 7, None) == "supplier_payment"
    assert classify_payment("out", 7, "purchase_order") == "supplier_payment"


def test_everything_else_is_other():
    assert classify_payment("in", None, None) == "other"
    assert classify_payment("out", None, None) == "other"
    assert classify_payment("out", None, "purchase_order") == "other"


def test_every_result_is_a_known_kind():
    for direction in ("in", "out"):
        for party in (None, 1):
            for ref in (None, "expense", "sales_order", "purchase_order"):
                assert classify_payment(direction, party, ref) in PAYMENT_KINDS


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print("ok  ", name)
