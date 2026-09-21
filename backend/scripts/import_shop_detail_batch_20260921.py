"""One-off: the 2026-09-21 Shop Detail update -- confirmed directly with the
user after a full category-by-category reconciliation of the workbook
against production (see the 2026-09-21 conversation):

  Polish Glass Protector -- top up 8 existing items (some also gain a new
  compatible model, where the sheet's "/"-separated cell grew to include a
  model the existing item wasn't tagged with yet) and create 8 brand-new
  items. One row is deliberately EXCLUDED: the sheet cell "A3 (2016)/17"
  (299 pcs) -- neither token could be confidently resolved (not an
  iPhone-default sheet, "17" alone doesn't match an obvious Samsung model),
  and the user hasn't clarified it. Left out entirely; no catalog entries,
  no stock, for that row.

  Its Me UV Glass Protector -- an entirely new category. The workbook has a
  sheet tab "ITS ME UV" (product label "ITS ME UV GLASS" inside it) that was
  never wired into shop_detail_data.py's SHEET_TO_CATEGORY -- fixed in this
  same commit. All 33 rows / 3,174 pcs are new stock, all new items.

Model-name notes:
  - "51" in the Polish Glass "A20/A30/51" cell -> Samsung Galaxy A51 (already
    a catalog model; the general resolver had wrongly guessed "iPhone 51",
    which doesn't exist).
  - "SPARK 40PRO+/60PRO+" in Its Me UV Glass -> Tecno, not iPhone (the
    general resolver's bare-number-defaults-to-iPhone rule misfired again
    the same way it did for "51"). Primary token reuses the catalog's
    existing "Spark 40 Pro" model (no "+", matching how that model is
    already spelled elsewhere); the new compatible model is created as
    "Spark 60 Pro" for the same reason -- avoids adding a second, differently
    -spelled near-duplicate of an existing model.
  - Every other new model name below was cross-checked against the existing
    catalog first and reuses an exact existing spelling wherever one exists
    (Oppo F19, Samsung Galaxy S21 FE, iPhone 12 Pro Max/13/13 Pro, Huawei
    P30 Pro, Tecno Camon 50 Pro, Samsung Galaxy Note Edge, Infinix HOT 50
    PRO+/HOT 60 PRO+/ZERO 30/NOTE EDGE/Note 40 Pro, Samsung S8+/S9/S10+/S20+/
    S21 ULTRA/S22 ULTRA/S23 ULTRA/SAM NOTE 20 ULTRA, OnePlus 11, Vivo V29/
    V30/V30E/V40/V40E) -- this avoids adding fresh spelling-duplicates on top
    of the catalog's existing debt.

Run with the backend's own venv (needs the app's DB session/services):
    DATABASE_URL=... backend/.venv/bin/python scripts/import_shop_detail_batch_20260921.py [--apply]
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

POLISH_GLASS_RATE = Decimal("22.01")
ITS_ME_UV_RATE = Decimal("87.6")

CATEGORY_SKU_PREFIX = {
    "Polish Glass Protector": "POLGL",
    "Its Me UV Glass Protector": "ITSUV",
}

# --- Polish Glass Protector: top up existing items (item_id, qty added) ---
POLISH_GLASS_TOPUPS = [
    (474, Decimal(2458)),  # iPhone 12 Pro (compat iPhone 12) -- row "12 PRO/12" 2758 vs 300
    (460, Decimal(1700)),  # Samsung Galaxy A20 (compat A30) -- row "A20/A30/51" 3675 vs 1975
    (470, Decimal(1400)),  # Infinix Hot9 Play -- row "HOT 9 PLAY" 2475 vs 1075
    (482, Decimal(985)),   # Oppo Reno 2 -- row "F19/Reno 2" 1770 vs 785
    (900, Decimal(650)),   # Samsung A37 -- row "A37" 1300 vs 650
    (469, Decimal(410)),   # Samsung J510 -- row "J510" 510 vs 100
    (471, Decimal(150)),   # Huawei Y9PRIME (compat Oppo F11 Pro) -- row "Y9Prime/f11 pro" 300 vs 150
    (477, Decimal(45)),    # Tecno Paviour 4 -- row "PAVIOUR 4" 220 vs 175
]

# New compatible models to add to existing items whose sheet cell grew to
# cover a model they weren't tagged with yet (item_id, brand, model_name).
POLISH_GLASS_NEW_COMPAT = [
    (460, "Samsung", "Galaxy A51"),  # already a catalog model
    (482, "Oppo", "F19"),            # already a catalog model
]

# New items in Polish Glass Protector (brand, model, [compat brand/model], qty)
POLISH_GLASS_NEW_ITEMS = [
    ("iPhone", "iPhone 12 Pro Max", [], Decimal(1250)),
    ("Tecno", "Camon 18", [], Decimal(1100)),
    ("Vivo", "Y3 (2018)", [], Decimal(575)),
    ("Samsung", "J110", [("Samsung", "JACE")], Decimal(552)),
    ("iPhone", "iPhone 13", [], Decimal(350)),
    ("Samsung", "S7", [], Decimal(198)),
    ("Samsung", "Galaxy S21 FE", [], Decimal(50)),
    ("iPhone", "iPhone 13 Pro", [], Decimal(32)),
]
# EXCLUDED: sheet cell "A3 (2016)/17" (299 pcs) -- unresolved, not imported.

# Its Me UV Glass Protector: entirely new category, all new items
# (brand, model, [compat brand/model], qty)
ITS_ME_UV_ITEMS = [
    ("Huawei", "P30 Pro", [("Redmi", "C9 Pro")], Decimal(436)),
    ("OnePlus", "8 Pro", [], Decimal(35)),
    ("Tecno", "Camon 50 Pro", [], Decimal(637)),
    ("Samsung", "Galaxy Note Edge", [], Decimal(125)),
    ("Tecno", "Spark 40 Pro", [("Tecno", "Spark 60 Pro")], Decimal(258)),
    ("Samsung", "Note 8", [], Decimal(31)),
    ("Samsung", "S10+", [], Decimal(29)),
    ("Samsung", "Note 20", [], Decimal(66)),
    ("Samsung", "S8+", [], Decimal(5)),
    ("Samsung", "S21 ULTRA", [], Decimal(80)),
    ("Vivo", "V29", [], Decimal(10)),
    ("Samsung", "S20+", [], Decimal(4)),
    ("OnePlus", "11", [], Decimal(12)),
    ("OnePlus", "12 Pro", [], Decimal(17)),
    ("Samsung", "S9", [], Decimal(4)),
    ("Infinix", "Note 40 Pro", [], Decimal(50)),
    ("Infinix", "HOT 50 PRO+", [], Decimal(100)),
    ("Infinix", "HOT 60 PRO+", [], Decimal(250)),
    ("Infinix", "ZERO 30", [], Decimal(250)),
    ("Infinix", "NOTE EDGE", [], Decimal(100)),
    ("OnePlus", "9 Pro", [], Decimal(25)),
    ("OnePlus", "10 Pro", [], Decimal(25)),
    ("OnePlus", "8", [], Decimal(25)),
    ("Google Pixel", "Pixel 6 Pro", [], Decimal(100)),
    ("Google Pixel", "Pixel 7 Pro", [], Decimal(100)),
    ("Samsung", "S23 ULTRA", [], Decimal(125)),
    ("Samsung", "S22 ULTRA", [], Decimal(100)),
    ("Samsung", "SAM NOTE 20 ULTRA", [], Decimal(25)),
    ("Infinix", "Note 10+", [], Decimal(25)),
    ("Vivo", "V40", [], Decimal(25)),
    ("Vivo", "V40E", [], Decimal(50)),
    ("Vivo", "V30", [], Decimal(25)),
    ("Vivo", "V30E", [], Decimal(25)),
]


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


async def get_or_create_category(session, name: str) -> Category:
    existing = await session.scalar(select(Category).where(Category.name == name))
    if existing:
        return existing
    row = Category(name=name)
    session.add(row)
    await session.flush()
    print(f"Created Category '{name}'.")
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


async def add_compat_model_if_missing(session, item_id: int, brand: Brand, model: Model) -> bool:
    existing = await session.scalar(
        select(ItemCompatibleModel).where(
            ItemCompatibleModel.item_id == item_id, ItemCompatibleModel.model_id == model.id
        )
    )
    if existing:
        return False
    session.add(ItemCompatibleModel(item_id=item_id, model_id=model.id))
    await session.flush()
    print(f"  Linked item {item_id} as compatible with {brand.name} {model.name}.")
    return True


async def resolve_new_item(session, category: Category, brand_name: str, model_name: str, compat: list[tuple[str, str]]) -> Item:
    brand = await get_or_create_brand(session, brand_name)
    model = await get_or_create_model(session, brand, model_name)
    compat_models = []
    for cbrand, cmodel in compat:
        cb = await get_or_create_brand(session, cbrand)
        cm = await get_or_create_model(session, cb, cmodel)
        compat_models.append(cm)
    return await get_or_create_item(session, category, model, compat_models)


async def receive_po(session, mohsin, category_name: str, rate: Decimal, lines: list[tuple[int, Decimal]]) -> Decimal:
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
    return po_total


async def main(apply: bool) -> None:
    async with SessionLocal() as session:
        mohsin = await session.scalar(select(Party).where(Party.name == VENDOR_NAME))
        if not mohsin:
            raise RuntimeError(f"Party '{VENDOR_NAME}' not found -- expected to already exist")

        polish_glass = await session.scalar(select(Category).where(Category.name == "Polish Glass Protector"))
        if not polish_glass:
            raise RuntimeError("Category 'Polish Glass Protector' not found -- expected to already exist")

        # --- verify top-up targets exist before touching anything ---
        topup_lines: list[tuple[int, Decimal]] = []
        for item_id, qty in POLISH_GLASS_TOPUPS:
            item = await session.get(Item, item_id)
            if item is None or item.category_id != polish_glass.id:
                raise RuntimeError(f"Item {item_id} not found in Polish Glass Protector -- aborting")
            topup_lines.append((item_id, qty))

        # --- add new compatible models to existing items ---
        new_compat_plan = []
        for item_id, brand_name, model_name in POLISH_GLASS_NEW_COMPAT:
            brand = await get_or_create_brand(session, brand_name)
            model = await get_or_create_model(session, brand, model_name)
            new_compat_plan.append((item_id, brand, model))
        await session.commit()

        # --- resolve new Polish Glass items ---
        new_item_lines: list[tuple[int, Decimal]] = []
        for brand_name, model_name, compat, qty in POLISH_GLASS_NEW_ITEMS:
            item = await resolve_new_item(session, polish_glass, brand_name, model_name, compat)
            new_item_lines.append((item.id, qty))
        await session.commit()

        # --- resolve Its Me UV Glass Protector (new category, all new items) ---
        its_me_uv = await get_or_create_category(session, "Its Me UV Glass Protector")
        await session.commit()
        its_me_uv_lines: list[tuple[int, Decimal]] = []
        for brand_name, model_name, compat, qty in ITS_ME_UV_ITEMS:
            item = await resolve_new_item(session, its_me_uv, brand_name, model_name, compat)
            its_me_uv_lines.append((item.id, qty))
        await session.commit()

        polish_glass_all_lines = topup_lines + new_item_lines
        polish_glass_total = sum(q for _i, q in polish_glass_all_lines)
        its_me_uv_total = sum(q for _i, q in its_me_uv_lines)

        if not apply:
            print(f"\n[DRY RUN] Polish Glass Protector PO: {len(polish_glass_all_lines)} lines, total qty {polish_glass_total}")
            print(f"[DRY RUN]   {len(POLISH_GLASS_NEW_COMPAT)} new compatible-model links would be added:")
            for item_id, brand, model in new_compat_plan:
                print(f"[DRY RUN]     item {item_id} <-> {brand.name} {model.name}")
            print(f"[DRY RUN] Its Me UV Glass Protector PO: {len(its_me_uv_lines)} lines, total qty {its_me_uv_total}")
            print("[DRY RUN] Excluded: sheet row 'A3 (2016)/17' (299 pcs) -- unresolved, not imported.")
            print("\nDRY RUN -- catalog rows above were created for real (get-or-create is idempotent-safe on "
                  "re-run), but no purchase orders, receipts, or ledger entries were created. Re-run with --apply to commit.")
            return

        # --- link new compatible models onto existing items ---
        for item_id, brand, model in new_compat_plan:
            await add_compat_model_if_missing(session, item_id, brand, model)
        await session.commit()

        pg_total = await receive_po(session, mohsin, "Polish Glass Protector", POLISH_GLASS_RATE, polish_glass_all_lines)
        uv_total = await receive_po(session, mohsin, "Its Me UV Glass Protector", ITS_ME_UV_RATE, its_me_uv_lines)

        print(f"Done. Polish Glass Protector: {polish_glass_total} pcs received, {pg_total} PKR.")
        print(f"Its Me UV Glass Protector: {its_me_uv_total} pcs received, {uv_total} PKR.")
        print("Accounts Payable to Mohsin offset back to zero for both POs.")
        print("Excluded: sheet row 'A3 (2016)/17' (299 pcs) -- unresolved, not imported.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.apply))
