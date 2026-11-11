"""Checks for inventory.service.plan_consumption - the rule: own item's lots first, then items that also fit.

Run with pytest if installed, or directly:  python tests/test_stock_consumption.py   (from backend/)
"""
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.inventory.exceptions import InsufficientStock  # noqa: E402
from src.inventory.service import LotView, plan_consumption  # noqa: E402

OWN, OTHER_A, OTHER_B = 1, 2, 3


def lot(lot_id, item_id, qty, received, cost="50.00"):
    return LotView(lot_id, item_id, Decimal(qty), date.fromisoformat(received), Decimal(cost))


def taken(plan):
    return [(p.stock_lot_id, str(p.qty_consumed)) for p in plan]


def test_own_stock_is_enough_and_oldest_lot_goes_first():
    lots = [lot(11, OWN, "10", "2026-09-10"), lot(10, OWN, "10", "2026-09-01"), lot(20, OTHER_A, "100", "2026-08-01")]
    assert taken(plan_consumption(OWN, lots, Decimal("15"))) == [(10, "10"), (11, "5")]


def test_own_first_even_when_a_fitting_lot_is_older():
    lots = [lot(20, OTHER_A, "50", "2026-01-01"), lot(10, OWN, "5", "2026-09-01")]
    assert taken(plan_consumption(OWN, lots, Decimal("5"))) == [(10, "5")]


def test_continues_with_fitting_items_oldest_first_across_items():
    lots = [
        lot(10, OWN, "4", "2026-09-01"),
        lot(21, OTHER_B, "10", "2026-08-15"),  # older than the other fitting lot
        lot(20, OTHER_A, "10", "2026-09-05"),
    ]
    assert taken(plan_consumption(OWN, lots, Decimal("20"))) == [(10, "4"), (21, "10"), (20, "6")]


def test_exact_exhaustion_and_cost_is_each_lots_own():
    lots = [lot(10, OWN, "3", "2026-09-01", "82.51"), lot(20, OTHER_A, "2", "2026-09-02", "90.00")]
    plan = plan_consumption(OWN, lots, Decimal("5"))
    assert taken(plan) == [(10, "3"), (20, "2")] and [str(p.unit_cost_pkr) for p in plan] == ["82.51", "90.00"]


def test_zero_stock_lots_are_skipped():
    lots = [lot(10, OWN, "0", "2026-09-01"), lot(11, OWN, "6", "2026-09-02"), lot(20, OTHER_A, "0", "2026-08-01")]
    assert taken(plan_consumption(OWN, lots, Decimal("6"))) == [(11, "6")]


def test_not_enough_in_total_raises_with_both_numbers():
    lots = [lot(10, OWN, "4", "2026-09-01"), lot(20, OTHER_A, "5", "2026-09-02")]
    try:
        plan_consumption(OWN, lots, Decimal("10"))
    except InsufficientStock as exc:
        assert "4" in str(exc.detail if hasattr(exc, "detail") else exc) or "4" in str(exc)
    else:
        raise AssertionError("expected InsufficientStock")


def test_no_fitting_stock_behaves_like_before():
    lots = [lot(10, OWN, "4", "2026-09-01")]
    try:
        plan_consumption(OWN, lots, Decimal("5"))
    except InsufficientStock:
        pass
    else:
        raise AssertionError("expected InsufficientStock")
    assert taken(plan_consumption(OWN, lots, Decimal("4"))) == [(10, "4")]


if __name__ == "__main__":
    failed = 0
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            try:
                fn()
                print("ok  ", name)
            except AssertionError as exc:
                failed += 1
                print("FAIL", name, "-", exc)
    sys.exit(1 if failed else 0)
