"""One-off data fix: reactivate catalog Model rows that are still referenced
by a real, active Item (directly via Item.model_id, or indirectly via
ItemCompatibleModel) but were left with is_active=False.

Root cause (found 2026-09-24 while investigating why "Hot 60 Pro" didn't
appear in the Inventory page's model search dropdown): several one-off import
scripts over time (this session's shop_detail batches included) reuse an
existing Model row by exact name match to avoid creating spelling-duplicates
-- a deliberate, correct choice -- but never checked whether the row they
matched was still active, and never reactivated it when it wasn't. The
generic CRUD list endpoint (which every model-picker combobox in the app
calls) always filters `is_active = True`, so these models silently vanished
from every dropdown even though real stock exists against them.

This script only flips is_active back to True on rows that are demonstrably
still in use -- it creates nothing and deletes nothing.

Run with the backend's own venv:
    DATABASE_URL=... backend/.venv/bin/python scripts/reactivate_orphaned_models.py [--apply]
"""

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend/ on sys.path

from sqlalchemy import select

# Every ORM model module must be imported before the first flush/commit.
from src.auth.models import User  # noqa: F401
from src.cargo.models import CargoAllocation, CargoCostBasis, CargoMode, CargoShipment  # noqa: F401
from src.catalog.models import Item, ItemCompatibleModel, Model
from src.database import SessionLocal
from src.expenses.models import Expense, ExpenseCategory, RecurringExpenseTemplate  # noqa: F401
from src.inventory.models import StockLot, StockMovement  # noqa: F401
from src.ledger.models import LedgerEntry  # noqa: F401
from src.models import Setting  # noqa: F401
from src.parties.models import Party  # noqa: F401
from src.payments.models import PaymentAccount, PaymentMethod, PaymentTransaction  # noqa: F401
from src.purchasing.models import ExchangeRate, PurchaseOrder, PurchaseOrderLine  # noqa: F401
from src.sales.models import SalesOrder, SalesOrderLine, SalesOrderLineLot  # noqa: F401


async def main(apply: bool) -> None:
    async with SessionLocal() as session:
        direct_ids = set(
            (
                await session.scalars(
                    select(Model.id)
                    .join(Item, Item.model_id == Model.id)
                    .where(Model.is_active.is_(False), Item.is_active.is_(True))
                    .distinct()
                )
            ).all()
        )
        compatible_ids = set(
            (
                await session.scalars(
                    select(Model.id)
                    .join(ItemCompatibleModel, ItemCompatibleModel.model_id == Model.id)
                    .join(Item, Item.id == ItemCompatibleModel.item_id)
                    .where(Model.is_active.is_(False), Item.is_active.is_(True))
                    .distinct()
                )
            ).all()
        )
        model_ids = sorted(direct_ids | compatible_ids)

        if not model_ids:
            print("Nothing to fix -- no inactive Model rows are referenced by an active Item.")
            return

        models = (await session.scalars(select(Model).where(Model.id.in_(model_ids)))).all()

        if not apply:
            print(f"[DRY RUN] Would reactivate {len(models)} Model row(s):")
            for m in sorted(models, key=lambda m: m.id):
                print(f"  id={m.id} name={m.name!r}")
            print("\nDRY RUN -- nothing written. Re-run with --apply to commit.")
            return

        for m in models:
            m.is_active = True
        await session.commit()
        print(f"Reactivated {len(models)} Model row(s): {sorted(m.id for m in models)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.apply))
