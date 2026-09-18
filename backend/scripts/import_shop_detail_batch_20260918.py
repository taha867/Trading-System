"""One-off: the 2026-09-18 Shop Detail update -- confirmed directly with the
user (not derived from an automated diff, which turned out to be too noisy
for categories with pre-existing duplicate-model-name debt):

  Polish Glass Protector (existing items get more stock; A37 is genuinely new):
    - Samsung Galaxy A20 (item 460): +1375
    - Infinix Hot9 Play (item 470): +900
    - Samsung A37 (new model): +650
    - Oppo Reno 2 (item 482): +635 ("F19" is the same phone as "Reno 2" --
      confirmed with the user -- no new item/model for "F19")

  Matt Privacy Glass Protector:
    - iPhone 17 Pro Max (item 676, already has 20 units from the original
      import): +46, bringing it to 66 -- matches the sheet's own total.

  Simple Privacy Protector -- a correction, not new stock: iPhone 14 Pro Max
  (item 694) has exactly one stock lot (id 562, from the very first import,
  untouched by any sale) recorded as 517 units; confirmed with the user the
  real number is 47. Corrects StockLot.qty_received/qty_remaining,
  PurchaseOrderLine.qty, and the Inventory ledger entry's debit in place --
  same "no void/reversal, no sales touched it" reasoning as expenses'
  update_expense and December's damaged-stock fixes this session. The
  Accounts Payable pair for that PO already nets to zero and isn't touched
  (whatever the credit/debit figure is, it still cancels to zero).

Run with the backend's own venv (needs the app's DB session/services):
    DATABASE_URL=... backend/.venv/bin/python scripts/import_shop_detail_batch_20260918.py [--apply]
"""

import argparse
import asyncio
import os
import sys
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend/ on sys.path

from sqlalchemy import select

# Every ORM model module must be imported before the first flush/commit.
from src.auth.models import User  # noqa: F401
from src.cargo.models import CargoAllocation, CargoCostBasis, CargoMode, CargoShipment  # noqa: F401
from src.catalog.models import Brand, Category, Item, ItemCompatibleModel, Model
from src.database import SessionLocal
from src.expenses.models import Expense, ExpenseCategory, RecurringExpenseTemplate  # noqa: F401
from src.inventory import service as inventory_service
from src.inventory.models import StockLot, StockMovement  # noqa: F401
from src.inventory.schemas import StockLotReceiveCreate
from src.ledger import service as ledger_service
from src.ledger.models import LedgerEntry
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
POLISH_GLASS_RATE = Decimal("22.01")
MATT_PRIVACY_RATE = Decimal("170.32")

# (item_id or None, brand, model, qty)
POLISH_GLASS_LINES = [
    (460, "Samsung", "Galaxy A20", Decimal(1375)),
    (470, "Infinix", "Hot9 Play", Decimal(900)),
    (None, "Samsung", "A37", Decimal(650)),  # new model
    (482, "Oppo", "Reno 2", Decimal(635)),   # "F19" == "Reno 2", confirmed with the user
]

MATT_PRIVACY_ITEM_ID = 676  # iPhone 17 Pro Max
MATT_PRIVACY_QTY = Decimal(46)

# Simple Privacy Protector correction
CORRECT_LOT_ID = 562
CORRECT_LINE_ID = 647
CORRECT_LEDGER_ID = 587
CORRECT_QTY = Decimal(47)


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


async def get_or_create_item(session, category: Category, model: Model) -> Item:
    existing = await session.scalar(
        select(Item).where(Item.category_id == category.id, Item.model_id == model.id, Item.variant.is_(None))
    )
    if existing:
        return existing
    sku = await unique_sku(session, f"POLGL-{slug(model.name)}")
    row = Item(category_id=category.id, model_id=model.id, sku=sku, variant=None)
    session.add(row)
    await session.flush()
    print(f"Created Item '{sku}' ({model.name}).")
    return row


async def receive_po(session, mohsin, category_name: str, rate: Decimal, lines: list[tuple[int, Decimal]]) -> None:
    lines_payload = [PurchaseOrderLineCreate(item_id=item_id, qty=qty, rate_pkr=rate) for item_id, qty in lines]
    po = await purchasing_service.create_purchase_order(
        session, PurchaseOrderCreate(party_id=mohsin.id, order_date=TODAY, source="local", lines=lines_payload)
    )
    print(f"Created PurchaseOrder #{po.id} for '{category_name}' ({len(lines_payload)} lines).")

    po_total = Decimal(0)
    for line in po.lines:
        lot = await inventory_service.receive_purchase_order_line(
            session, StockLotReceiveCreate(purchase_order_line_id=line.id, received_date=TODAY)
        )
        po_total += money(lot.qty_received * lot.landed_cost_pkr)
    po_total = money(po_total)

    await ledger_service.post_entry(
        session, entry_date=TODAY, account="Accounts Payable", debit=po_total,
        reference_type="purchase_order", reference_id=po.id, party_id=mohsin.id,
    )
    await session.commit()
    print(f"  Received all lines, offset Accounts Payable by {po_total} PKR.\n")


async def main(apply: bool) -> None:
    async with SessionLocal() as session:
        mohsin = await session.scalar(select(Party).where(Party.name == VENDOR_NAME))
        if not mohsin:
            raise RuntimeError(f"Party '{VENDOR_NAME}' not found -- expected to already exist")
        polish_glass = await session.scalar(select(Category).where(Category.name == "Polish Glass Protector"))
        if not polish_glass:
            raise RuntimeError("Category 'Polish Glass Protector' not found -- expected to already exist")

        # --- resolve Polish Glass lines (3 existing items + 1 new model) ---
        polish_glass_lines: list[tuple[int, Decimal]] = []
        for item_id, brand_name, model_name, qty in POLISH_GLASS_LINES:
            if item_id is not None:
                polish_glass_lines.append((item_id, qty))
                continue
            brand = await get_or_create_brand(session, brand_name)
            model = await get_or_create_model(session, brand, model_name)
            item = await get_or_create_item(session, polish_glass, model)
            polish_glass_lines.append((item.id, qty))
        await session.commit()

        # --- verify the correction target before touching it ---
        lot = await session.get(StockLot, CORRECT_LOT_ID)
        line = await session.get(PurchaseOrderLine, CORRECT_LINE_ID)
        entry = await session.get(LedgerEntry, CORRECT_LEDGER_ID)
        if lot is None or line is None or entry is None:
            raise RuntimeError("Correction target row(s) not found -- aborting")
        if lot.qty_remaining != lot.qty_received:
            raise RuntimeError(
                f"Lot {CORRECT_LOT_ID} has qty_remaining={lot.qty_remaining} != qty_received={lot.qty_received} "
                "-- something has already consumed from it, needs manual review before correcting"
            )
        from sqlalchemy import func
        from src.sales.models import SalesOrderLine
        sold_count = await session.scalar(
            select(func.count()).select_from(SalesOrderLine).where(SalesOrderLine.item_id == lot.item_id)
        )
        if sold_count:
            raise RuntimeError(f"Item {lot.item_id} has {sold_count} sales_order_line rows -- aborting")

        new_landed_cost = lot.landed_cost_pkr  # unchanged, only qty is wrong
        new_debit = money(CORRECT_QTY * new_landed_cost)

        if not apply:
            print("[DRY RUN] Polish Glass Protector PO:")
            for (item_id, _b, _m, qty), (resolved_item_id, _q) in zip(POLISH_GLASS_LINES, polish_glass_lines):
                print(f"  item {resolved_item_id}: +{qty}")
            print(f"[DRY RUN] Matt Privacy Glass Protector PO: item {MATT_PRIVACY_ITEM_ID}: +{MATT_PRIVACY_QTY}")
            print(
                f"[DRY RUN] Correct lot {CORRECT_LOT_ID} / line {CORRECT_LINE_ID} / ledger {CORRECT_LEDGER_ID}: "
                f"qty {lot.qty_received} -> {CORRECT_QTY}, ledger debit {entry.debit} -> {new_debit}"
            )
            print("\nDRY RUN -- nothing written. Re-run with --apply to commit.")
            return

        await receive_po(session, mohsin, "Polish Glass Protector", POLISH_GLASS_RATE, polish_glass_lines)
        await receive_po(session, mohsin, "Matt Privacy Glass Protector", MATT_PRIVACY_RATE, [(MATT_PRIVACY_ITEM_ID, MATT_PRIVACY_QTY)])

        old_qty, old_debit = lot.qty_received, entry.debit
        lot.qty_received = CORRECT_QTY
        lot.qty_remaining = CORRECT_QTY
        line.qty = CORRECT_QTY
        entry.debit = new_debit
        await session.commit()
        print(
            f"Corrected Simple Privacy Protector iPhone 14 Pro Max: qty {old_qty} -> {CORRECT_QTY}, "
            f"ledger debit {old_debit} -> {new_debit} PKR."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.apply))
