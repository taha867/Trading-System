"""One-off data fix: permanently DELETE soft-deleted catalog rows (Item,
Model, Brand) that have zero references anywhere in the database -- no
stock lot, purchase order line, sales order line, or compatible-model link
was ever created against them, at any time. Confirmed with the user
2026-09-24 after a full reference audit (see conversation).

This is the one and only place in this codebase that does a real
`DELETE FROM` on catalog rows -- everywhere else in the app, "delete" means
flip `is_active` to False (CLAUDE.md's "soft delete everywhere / history
must never break"). A row only qualifies here if it has NO history at all
to break: every check below only ever counts is_active=False rows as
candidates, and only removes one once every table that could reference it
(active or inactive) comes back empty.

Deletion order (FK-safe): item_compatible_model rows for the dead items ->
the dead items -> the dead models -> the dead brands. Each step re-queries
live database state rather than a fixed id list, so it stays correct even
if state has moved since the audit.

Run with the backend's own venv:
    DATABASE_URL=... backend/.venv/bin/python scripts/purge_orphaned_catalog_rows.py [--apply]
"""

import argparse
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend/ on sys.path

from sqlalchemy import delete, func, select

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
from src.purchasing.models import ExchangeRate, PurchaseOrder, PurchaseOrderLine
from src.sales.models import SalesOrder, SalesOrderLine, SalesOrderLineLot


async def find_orphaned_items(session) -> list[Item]:
    referenced_by_stock = select(StockLot.item_id).distinct()
    referenced_by_po_line = select(PurchaseOrderLine.item_id).distinct()
    referenced_by_so_line = select(SalesOrderLine.item_id).distinct()
    stmt = select(Item).where(
        Item.is_active.is_(False),
        Item.id.not_in(referenced_by_stock),
        Item.id.not_in(referenced_by_po_line),
        Item.id.not_in(referenced_by_so_line),
    )
    return list((await session.scalars(stmt)).all())


async def find_orphaned_models(session) -> list[Model]:
    referenced_by_item = select(Item.model_id).distinct()
    referenced_by_compatible = select(ItemCompatibleModel.model_id).distinct()
    stmt = select(Model).where(
        Model.is_active.is_(False),
        Model.id.not_in(referenced_by_item),
        Model.id.not_in(referenced_by_compatible),
    )
    return list((await session.scalars(stmt)).all())


async def find_orphaned_brands(session) -> list[Brand]:
    referenced_by_model = select(Model.brand_id).distinct()
    stmt = select(Brand).where(Brand.is_active.is_(False), Brand.id.not_in(referenced_by_model))
    return list((await session.scalars(stmt)).all())


async def main(apply: bool) -> None:
    async with SessionLocal() as session:
        orphaned_items = await find_orphaned_items(session)
        item_ids = [i.id for i in orphaned_items]

        if not apply:
            print(f"[DRY RUN] {len(orphaned_items)} orphaned Item(s) would be deleted:")
            for i in sorted(orphaned_items, key=lambda i: i.id):
                print(f"  item id={i.id} sku={i.sku!r}")

            compat_count = 0
            if item_ids:
                compat_count = (
                    await session.scalar(
                        select(func.count())
                        .select_from(ItemCompatibleModel)
                        .where(ItemCompatibleModel.item_id.in_(item_ids))
                    )
                    or 0
                )
            print(f"\n[DRY RUN] Deleting these items would also remove {compat_count} item_compatible_model row(s).")

            # Preview models/brands as if the items above were already gone -- can't
            # literally do that in a dry run, so simulate by excluding item_ids from
            # the "referenced_by_item" set.
            referenced_by_item_excl = (
                select(Item.model_id).where(Item.model_id.is_not(None), Item.id.not_in(item_ids or [-1])).distinct()
            )
            referenced_by_compatible_excl = (
                select(ItemCompatibleModel.model_id).where(ItemCompatibleModel.item_id.not_in(item_ids or [-1])).distinct()
            )
            model_stmt = select(Model).where(
                Model.is_active.is_(False),
                Model.id.not_in(referenced_by_item_excl),
                Model.id.not_in(referenced_by_compatible_excl),
            )
            orphaned_models_preview = list((await session.scalars(model_stmt)).all())
            print(f"\n[DRY RUN] {len(orphaned_models_preview)} orphaned Model(s) would then be deleted:")
            for m in sorted(orphaned_models_preview, key=lambda m: m.id):
                print(f"  model id={m.id} name={m.name!r}")

            model_ids_preview = {m.id for m in orphaned_models_preview}
            referenced_by_model_excl = (
                select(Model.brand_id).where(Model.id.not_in(model_ids_preview or {-1})).distinct()
            )
            brand_stmt = select(Brand).where(Brand.is_active.is_(False), Brand.id.not_in(referenced_by_model_excl))
            orphaned_brands_preview = list((await session.scalars(brand_stmt)).all())
            print(f"\n[DRY RUN] {len(orphaned_brands_preview)} orphaned Brand(s) would then be deleted:")
            for b in sorted(orphaned_brands_preview, key=lambda b: b.id):
                print(f"  brand id={b.id} name={b.name!r}")

            print("\nDRY RUN -- nothing written. Re-run with --apply to commit.")
            return

        # 1. item_compatible_model rows for the dead items
        if item_ids:
            result = await session.execute(
                delete(ItemCompatibleModel).where(ItemCompatibleModel.item_id.in_(item_ids))
            )
            print(f"Deleted {result.rowcount} item_compatible_model row(s).")

        # 2. the dead items themselves
        if item_ids:
            await session.execute(delete(Item).where(Item.id.in_(item_ids)))
            print(f"Deleted {len(item_ids)} Item row(s).")
        await session.flush()

        # 3. models now orphaned (re-query live state, per the module docstring)
        orphaned_models = await find_orphaned_models(session)
        model_ids = [m.id for m in orphaned_models]
        if model_ids:
            await session.execute(delete(Model).where(Model.id.in_(model_ids)))
            print(f"Deleted {len(model_ids)} Model row(s): {sorted(model_ids)}")
        await session.flush()

        # 4. brands now orphaned
        orphaned_brands = await find_orphaned_brands(session)
        brand_ids = [b.id for b in orphaned_brands]
        if brand_ids:
            await session.execute(delete(Brand).where(Brand.id.in_(brand_ids)))
            print(f"Deleted {len(brand_ids)} Brand row(s): {sorted(brand_ids)}")

        await session.commit()
        print("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.apply))
