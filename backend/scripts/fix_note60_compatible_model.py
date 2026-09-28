"""One-off data fix: Item 306 (TPU-NOTE60, Infinix "Note 60") has a
compatible-model link pointing to "iPhone 60 Pro" (model id 273, under the
iPhone brand) -- a pre-existing data-entry bug flagged during the
2026-09-28 TPU Case import but deliberately left untouched at the time
since it was unrelated to that batch. Confirmed with the user: the correct
link is Infinix "Note 60 Pro" (model id 189, already in the catalog).

This only repoints the existing item_compatible_model row -- no new
catalog rows, no quantity/stock impact.

Run with the backend's own venv:
    DATABASE_URL=... backend/.venv/bin/python scripts/fix_note60_compatible_model.py [--apply]
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
from src.catalog.models import Brand, Category, Item, ItemCompatibleModel, Model
from src.database import SessionLocal
from src.expenses.models import Expense, ExpenseCategory, RecurringExpenseTemplate  # noqa: F401
from src.inventory.models import StockLot, StockMovement  # noqa: F401
from src.ledger.models import LedgerEntry  # noqa: F401
from src.models import Setting  # noqa: F401
from src.parties.models import Party  # noqa: F401
from src.payments.models import PaymentAccount, PaymentMethod, PaymentTransaction  # noqa: F401
from src.purchasing.models import ExchangeRate, PurchaseOrder, PurchaseOrderLine  # noqa: F401
from src.sales.models import SalesOrder, SalesOrderLine, SalesOrderLineLot  # noqa: F401

ITEM_ID = 306
WRONG_MODEL_ID = 273  # "iPhone 60 Pro"
CORRECT_MODEL_ID = 189  # Infinix "Note 60 Pro"


async def main(apply: bool) -> None:
    async with SessionLocal() as session:
        item = await session.get(Item, ITEM_ID)
        if item is None:
            raise RuntimeError(f"Item {ITEM_ID} not found -- aborting")

        link = await session.scalar(
            select(ItemCompatibleModel).where(
                ItemCompatibleModel.item_id == ITEM_ID, ItemCompatibleModel.model_id == WRONG_MODEL_ID
            )
        )
        if link is None:
            raise RuntimeError(
                f"No item_compatible_model row for item {ITEM_ID} -> model {WRONG_MODEL_ID} -- "
                "already fixed, or state has moved since this script was written. Aborting."
            )

        correct_model = await session.get(Model, CORRECT_MODEL_ID)
        if correct_model is None:
            raise RuntimeError(f"Model {CORRECT_MODEL_ID} (expected 'Note 60 Pro') not found -- aborting")

        if not apply:
            print(
                f"[DRY RUN] Would repoint item {ITEM_ID}'s compatible-model link: "
                f"model {WRONG_MODEL_ID} ('iPhone 60 Pro') -> model {CORRECT_MODEL_ID} ('{correct_model.name}')"
            )
            print("\nDRY RUN -- nothing written. Re-run with --apply to commit.")
            return

        link.model_id = CORRECT_MODEL_ID
        await session.commit()
        print(f"Repointed item {ITEM_ID}'s compatible-model link to model {CORRECT_MODEL_ID} ('{correct_model.name}').")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.apply))
