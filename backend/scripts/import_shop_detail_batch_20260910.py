"""One-off: import the 2026-09-10 Shop Detail update -- new/increased stock
across Dust Plug, Polish Glass, and UV Glass Protector, plus the Dust Plug
"DAMAG YELLOW PCS" section (both its 2 pre-existing entries, already sitting
in production as regular stock from the original import, and 13 brand-new
damage-only entries).

Reads the curated plan at SHOP_DETAIL_PLAN_JSON (built by diffing the
current preview CSV against the one from the original import -- see the
2026-09-10 conversation for how new_import/edited_import/damage_new were
derived) and the resolved-token CSV at SHOP_DETAIL_RESOLVED_CSV (Phase 1
preview output, same shape as shop_detail_preview.py always produces).

For new_import/edited_import rows: one PurchaseOrder per category (source=
local, vendor=Mohsin, category-average rate -- same convention as the
original import), lines received into StockLots, resulting Accounts Payable
offset back to zero (confirmed with the user: not a real debt, same
treatment as before).

For damage_new rows: received the same way, then immediately marked fully
damaged via inventory_service.mark_stock_lot_damaged (new in this session).
For the 2 pre-existing damage entries (Redmi Note11 Pro, Infinix Smart 4):
no new receipt -- their existing StockLots (ids hardcoded below, confirmed
via a read-only query first) are marked damaged directly.

Run with the backend's own venv (needs the app's DB session/services):
    DATABASE_URL=... backend/.venv/bin/python scripts/import_shop_detail_batch_20260910.py [--apply]
"""

import argparse
import asyncio
import csv
import json
import os
import sys
from collections import defaultdict
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend/ on sys.path

from sqlalchemy import select

# Every ORM model module must be imported before the first flush/commit --
# same reasoning as import_shop_detail.py and add_dust_plug_stock_batch.py.
from src.auth.models import User  # noqa: F401
from src.cargo.models import CargoAllocation, CargoCostBasis, CargoMode, CargoShipment  # noqa: F401
from src.catalog.models import Brand, Category, Item, ItemCompatibleModel, Model
from src.database import SessionLocal
from src.expenses.models import Expense, ExpenseCategory, RecurringExpenseTemplate  # noqa: F401
from src.inventory import service as inventory_service
from src.inventory.models import StockLot, StockMovement  # noqa: F401
from src.inventory.schemas import StockLotDamageCreate, StockLotReceiveCreate
from src.ledger import service as ledger_service
from src.ledger.models import LedgerEntry  # noqa: F401
from src.models import Setting  # noqa: F401
from src.parties.models import Party
from src.payments.models import PaymentAccount, PaymentMethod, PaymentTransaction  # noqa: F401
from src.purchasing import service as purchasing_service
from src.purchasing.models import ExchangeRate, PurchaseOrder, PurchaseOrderLine  # noqa: F401
from src.purchasing.schemas import PurchaseOrderCreate, PurchaseOrderLineCreate
from src.purchasing.utils import money
from src.sales.models import SalesOrder, SalesOrderLine, SalesOrderLineLot  # noqa: F401

VENDOR_NAME = "Mohsin"
TODAY = date.today()
PLAN_JSON = os.environ.get(
    "SHOP_DETAIL_PLAN_JSON",
    "/tmp/claude-1000/-home-m-taha-Desktop-shakeel/7b4afe99-4308-447c-a9e0-88dd968f66fa/scratchpad/final_import_plan.json",
)
RESOLVED_CSV = os.environ.get(
    "SHOP_DETAIL_RESOLVED_CSV",
    "/tmp/claude-1000/-home-m-taha-Desktop-shakeel/7b4afe99-4308-447c-a9e0-88dd968f66fa/scratchpad/shop_detail_preview_new.csv",
)

# The 2 damage-section entries that already exist in production as regular
# (undamaged) stock lots from the original import -- confirmed via a
# read-only query: both lots' qty_remaining still equals qty_received, so
# nothing has sold from them and it's safe to mark the full lot damaged.
EXISTING_DAMAGE_LOTS = [
    (279, Decimal(40), "Redmi NOTE11 Pro -- turned yellow (sheet's DAMAG YELLOW PCS section)"),
    (280, Decimal(5), "Infinix Smart 4 -- turned yellow (sheet's DAMAG YELLOW PCS section)"),
]

CATEGORY_SKU_PREFIX = {
    "Dust Plug": "DPLUG",
    "Polish Glass Protector": "POLGL",
    "UV Glass Protector": "UVGLS",
}


def slug(text: str) -> str:
    return "".join(c for c in text.upper() if c.isalnum())


async def get_or_create_brand(session, name: str) -> Brand:
    existing = await session.scalar(select(Brand).where(Brand.name == name))
    if existing:
        return existing
    row = Brand(name=name)
    session.add(row)
    await session.flush()
    print(f"Created Brand '{name}'.")
    return row


async def get_or_create_model(session, brand: Brand, name: str) -> Model:
    existing = await session.scalar(select(Model).where(Model.brand_id == brand.id, Model.name == name))
    if existing:
        return existing
    row = Model(brand_id=brand.id, name=name)
    session.add(row)
    await session.flush()
    print(f"Created Model '{brand.name} {name}'.")
    return row


async def unique_sku(session, base: str) -> str:
    candidate = base
    n = 2
    while await session.scalar(select(Item.id).where(Item.sku == candidate)):
        candidate = f"{base}-{n}"
        n += 1
    return candidate


async def get_or_create_item(session, category: Category, model: Model, compatible_models: list[Model]) -> Item:
    existing = await session.scalar(
        select(Item).where(Item.category_id == category.id, Item.model_id == model.id, Item.variant.is_(None))
    )
    if existing:
        return existing
    prefix = CATEGORY_SKU_PREFIX[category.name]
    sku = await unique_sku(session, f"{prefix}-{slug(model.name)}")
    row = Item(category_id=category.id, model_id=model.id, sku=sku, variant=None, compatible_models=compatible_models)
    session.add(row)
    await session.flush()
    print(f"Created Item '{sku}' ({model.name}).")
    return row


def load_resolved_rows(path: str) -> dict[tuple[str, str], list[dict]]:
    groups = defaultdict(list)
    with open(path) as f:
        for row in csv.DictReader(f):
            groups[(row["sheet"], row["row_id"])].append(row)
    return groups


async def get_or_create_category(session, name: str) -> Category:
    existing = await session.scalar(select(Category).where(Category.name == name))
    if existing:
        return existing
    row = Category(name=name)
    session.add(row)
    await session.flush()
    print(f"Created Category '{name}'.")
    return row


async def resolve_item_for_row(session, resolved_rows, sheet: str, row_id: str, category_cache, brand_cache, model_cache) -> Item:
    tokens = resolved_rows[(sheet, row_id)]
    category_name = tokens[0]["category"]
    if category_name not in category_cache:
        # UV Glass Protector is brand new in this batch -- its sheet was
        # entirely empty during the original import (confirmed: 0 rows in
        # that run's preview CSV), so get-or-create here, not a hard lookup.
        category_cache[category_name] = await get_or_create_category(session, category_name)
    category = category_cache[category_name]

    async def model_for(brand_name: str, model_name: str) -> Model:
        key = (brand_name, model_name)
        if key not in model_cache:
            if brand_name not in brand_cache:
                brand_cache[brand_name] = await get_or_create_brand(session, brand_name)
            model_cache[key] = await get_or_create_model(session, brand_cache[brand_name], model_name)
        return model_cache[key]

    primary = tokens[0]
    primary_model = await model_for(primary["brand"], primary["model"])
    compatible = []
    seen = set()
    for tok in tokens[1:]:
        key = (tok["brand"], tok["model"])
        if key == (primary["brand"], primary["model"]) or key in seen:
            continue
        seen.add(key)
        compatible.append(await model_for(tok["brand"], tok["model"]))

    return await get_or_create_item(session, category, primary_model, compatible)


async def main(apply: bool) -> None:
    plan = json.load(open(PLAN_JSON))
    resolved_rows = load_resolved_rows(RESOLVED_CSV)

    async with SessionLocal() as session:
        mohsin = await session.scalar(select(Party).where(Party.name == VENDOR_NAME))
        if not mohsin:
            raise RuntimeError(f"Party '{VENDOR_NAME}' not found -- expected to already exist")

        category_cache: dict[str, Category] = {}
        brand_cache: dict[str, Brand] = {}
        model_cache: dict[tuple[str, str], Model] = {}

        # --- resolve catalog for every row (new stock + edits + new damage) ---
        by_category: dict[str, list[tuple[Item, Decimal]]] = defaultdict(list)
        damage_new_items: list[tuple[Item, Decimal]] = []

        for category, sheet, row_id, qty, kind in plan["new_import"]:
            item = await resolve_item_for_row(session, resolved_rows, sheet, row_id, category_cache, brand_cache, model_cache)
            by_category[category].append((item, Decimal(str(qty))))

        for _category, sheet, row_id, qty, kind, _text in plan["edited_import"]:
            item = await resolve_item_for_row(session, resolved_rows, sheet, row_id, category_cache, brand_cache, model_cache)
            real_category = resolved_rows[(sheet, row_id)][0]["category"]
            by_category[real_category].append((item, Decimal(str(qty))))

        for sheet, row_id, qty in plan["damage_new"]:
            item = await resolve_item_for_row(session, resolved_rows, sheet, row_id, category_cache, brand_cache, model_cache)
            damage_new_items.append((item, Decimal(str(qty))))

        await session.commit()
        print(f"\nCatalog phase done. Categories: {list(by_category)}. Damage-new items: {len(damage_new_items)}.\n")

        if not apply:
            for category, lines in by_category.items():
                total = sum(q for _i, q in lines)
                print(f"[DRY RUN] Would create PO for '{category}': {len(lines)} lines, total qty {total}")
            total_damage_new = sum(q for _i, q in damage_new_items)
            print(f"[DRY RUN] Would receive-then-damage {len(damage_new_items)} new lines, total qty {total_damage_new}")
            print(f"[DRY RUN] Would mark {len(EXISTING_DAMAGE_LOTS)} existing lots fully damaged")
            print("\nDRY RUN -- no purchase orders, receipts, or damage records created. Re-run with --apply to commit.")
            return

        # --- rates (category average, same as the original import) ---
        rate_by_category = {
            "Dust Plug": Decimal("82.51"),
            "Polish Glass Protector": Decimal("22.01"),
            "UV Glass Protector": Decimal("88.44"),
        }

        total_qty_all = Decimal(0)
        total_value_all = Decimal(0)

        for category, lines in by_category.items():
            rate = rate_by_category[category]
            lines_payload = [
                PurchaseOrderLineCreate(item_id=item.id, qty=qty, rate_pkr=rate) for item, qty in lines
            ]
            po = await purchasing_service.create_purchase_order(
                session,
                PurchaseOrderCreate(party_id=mohsin.id, order_date=TODAY, source="local", lines=lines_payload),
            )
            print(f"Created PurchaseOrder #{po.id} for '{category}' ({len(lines_payload)} lines).")

            po_total = Decimal(0)
            for line in po.lines:
                lot = await inventory_service.receive_purchase_order_line(
                    session, StockLotReceiveCreate(purchase_order_line_id=line.id, received_date=TODAY)
                )
                po_total += money(lot.qty_received * lot.landed_cost_pkr)
                total_qty_all += lot.qty_received
            po_total = money(po_total)

            await ledger_service.post_entry(
                session, entry_date=TODAY, account="Accounts Payable", debit=po_total,
                reference_type="purchase_order", reference_id=po.id, party_id=mohsin.id,
            )
            await session.commit()
            total_value_all += po_total
            print(f"  Received all lines, offset Accounts Payable by {po_total} PKR.\n")

        # --- new damage entries: receive into Dust Plug, then mark fully damaged ---
        if damage_new_items:
            rate = rate_by_category["Dust Plug"]
            lines_payload = [
                PurchaseOrderLineCreate(item_id=item.id, qty=qty, rate_pkr=rate) for item, qty in damage_new_items
            ]
            po = await purchasing_service.create_purchase_order(
                session,
                PurchaseOrderCreate(party_id=mohsin.id, order_date=TODAY, source="local", lines=lines_payload),
            )
            print(f"Created PurchaseOrder #{po.id} for new damaged Dust Plug stock ({len(lines_payload)} lines).")

            po_total = Decimal(0)
            for line in po.lines:
                lot = await inventory_service.receive_purchase_order_line(
                    session, StockLotReceiveCreate(purchase_order_line_id=line.id, received_date=TODAY)
                )
                po_total += money(lot.qty_received * lot.landed_cost_pkr)
                total_qty_all += lot.qty_received
                await inventory_service.mark_stock_lot_damaged(
                    session,
                    StockLotDamageCreate(
                        stock_lot_id=lot.id,
                        qty=lot.qty_received,
                        reason="Turned yellow (received damaged, sheet's DAMAG YELLOW PCS section)",
                        movement_date=TODAY,
                    ),
                )
            po_total = money(po_total)

            await ledger_service.post_entry(
                session, entry_date=TODAY, account="Accounts Payable", debit=po_total,
                reference_type="purchase_order", reference_id=po.id, party_id=mohsin.id,
            )
            await session.commit()
            total_value_all += po_total
            print(f"  Received and marked damaged. Offset Accounts Payable by {po_total} PKR.\n")

        # --- existing damage entries: mark already-received lots damaged directly ---
        for lot_id, qty, reason in EXISTING_DAMAGE_LOTS:
            await inventory_service.mark_stock_lot_damaged(
                session, StockLotDamageCreate(stock_lot_id=lot_id, qty=qty, reason=reason, movement_date=TODAY)
            )
            await session.commit()
            print(f"Marked {qty} units of existing lot #{lot_id} damaged.")

        print(f"\nDone. Total qty received (new stock + new damage): {total_qty_all}. "
              f"Total inventory value added: {total_value_all} PKR.")
        print("Accounts Payable to Mohsin offset back to zero for every PO created above.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.apply))
