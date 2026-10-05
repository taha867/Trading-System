"""One-off data fix: TPU Case has two items representing the same iPhone
5/5s/SE compatible group, from two different import passes:
  - Item 946 "TPU-IPHONE5S" (model "iPhone 5s", correctly linked to
    compatible models "iPhone 5"/"iPhone SE") -- 50 pcs, correct.
  - Item 276 "TPU-IPHONE50" (model "iPhone 50", wrongly linked to a bogus
    "iPhone 55") -- 20 pcs, a garbled duplicate from an earlier import that
    mis-resolved the sheet's "5G/5S/5SE" token into nonsense model names.
Confirmed with the user 2026-10-?? after they spotted "iPhone 50"/"55" on
the TPU Case "Available Models" flyer and asked for the long-term fix
(not just a rename, which would have left two items claiming to be the
same phone).

This moves item 276's single stock lot (id 108, 20 pcs, untouched since
receipt -- no sales/damage movements) onto item 946, then soft-deactivates
item 276 and the two bogus models (254 "iPhone 50", 255 "iPhone 55"). Per
CLAUDE.md's soft-delete convention, nothing is hard-deleted: item 276 keeps
its real purchase/ledger history, it's just marked inactive so it stops
appearing anywhere (including the Available Models flyer).

Run with the backend's own venv:
    DATABASE_URL=... backend/.venv/bin/python scripts/merge_iphone50_55_into_5s.py [--apply]
"""

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend/ on sys.path

from sqlalchemy import func, select

# Every ORM model module must be imported before the first flush/commit.
from src.auth.models import User  # noqa: F401
from src.cargo.models import CargoAllocation, CargoCostBasis, CargoMode, CargoShipment  # noqa: F401
from src.catalog.models import Brand, Category, Item, ItemCompatibleModel, Model  # noqa: F401
from src.database import SessionLocal
from src.expenses.models import Expense, ExpenseCategory, RecurringExpenseTemplate  # noqa: F401
from src.inventory.models import StockLot, StockMovement  # noqa: F401
from src.ledger.models import LedgerEntry  # noqa: F401
from src.models import Setting  # noqa: F401
from src.parties.models import Party  # noqa: F401
from src.payments.models import PaymentAccount, PaymentMethod, PaymentTransaction  # noqa: F401
from src.purchasing.models import ExchangeRate, PurchaseOrder, PurchaseOrderLine  # noqa: F401
from src.sales.models import SalesOrder, SalesOrderLine, SalesOrderLineLot  # noqa: F401

BROKEN_ITEM_ID = 276  # TPU-IPHONE50
CORRECT_ITEM_ID = 946  # TPU-IPHONE5S
BROKEN_MODEL_IDS = [254, 255]  # "iPhone 50", "iPhone 55"


async def main(apply: bool) -> None:
    async with SessionLocal() as session:
        broken_item = await session.get(Item, BROKEN_ITEM_ID)
        correct_item = await session.get(Item, CORRECT_ITEM_ID)
        if broken_item is None or correct_item is None:
            raise RuntimeError("Expected items not found -- aborting")
        if not broken_item.is_active or not correct_item.is_active:
            raise RuntimeError("One of the items is already inactive -- state has moved, aborting")

        lots = (await session.scalars(select(StockLot).where(StockLot.item_id == BROKEN_ITEM_ID))).all()
        sold_count = await session.scalar(
            select(func.count()).select_from(StockMovement).join(StockLot).where(
                StockLot.item_id == BROKEN_ITEM_ID, StockMovement.movement_type != "receipt"
            )
        )
        if sold_count:
            raise RuntimeError(
                f"Item {BROKEN_ITEM_ID} has {sold_count} non-receipt stock movement(s) -- "
                "needs manual review before merging, aborting"
            )

        moved_qty = sum(lot.qty_received for lot in lots)

        if not apply:
            print(f"[DRY RUN] Would move {len(lots)} stock lot(s) ({moved_qty} pcs) from item {BROKEN_ITEM_ID} to {CORRECT_ITEM_ID}")
            for lot in lots:
                print(f"  lot {lot.id}: {lot.qty_received} pcs received {lot.received_date}")
            print(f"[DRY RUN] Would deactivate item {BROKEN_ITEM_ID} ({broken_item.sku})")
            print(f"[DRY RUN] Would deactivate models {BROKEN_MODEL_IDS}")
            print("\nDRY RUN -- nothing written. Re-run with --apply to commit.")
            return

        for lot in lots:
            lot.item_id = CORRECT_ITEM_ID
            print(f"Moved lot {lot.id} ({lot.qty_received} pcs) -> item {CORRECT_ITEM_ID}.")

        broken_item.is_active = False
        print(f"Deactivated item {BROKEN_ITEM_ID} ({broken_item.sku}).")

        for model_id in BROKEN_MODEL_IDS:
            model = await session.get(Model, model_id)
            if model is None:
                raise RuntimeError(f"Model {model_id} not found -- aborting")
            model.is_active = False
            print(f"Deactivated model {model_id} ('{model.name}').")

        await session.commit()

        new_total = await session.scalar(
            select(func.sum(StockLot.qty_received)).where(StockLot.item_id == CORRECT_ITEM_ID)
        )
        print(f"\nDone. Item {CORRECT_ITEM_ID} ({correct_item.sku}) now has {new_total} pcs total received.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.apply))
