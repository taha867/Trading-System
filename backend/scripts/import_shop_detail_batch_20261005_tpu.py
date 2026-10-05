"""One-off: the 2026-10-05 Shop Detail update -- more TPU Case stock
received from Mohsin, on top of the 2026-10-01 batch already in
production (script: import_shop_detail_batch_20261001_tpu.py, which
brought TPU Case to 10,187 pcs received). Confirmed with the user after
a fresh row-by-row reconciliation of the TPU sheet against production
(see the 2026-10-05 conversation) -- quantities were independently
re-typed by the user twice and matched exactly both times.

Summary of the reconciliation (sheet grand total now 11,455 pcs,
production baseline before this batch 10,187 pcs, gap 1,268 pcs):
  - iPhone, Samsung, Google Pixel, Tecno, Infinix, Itel sections: 100%
    match, zero changes.
  - 1 existing item gets a quantity top-up + an added compatible model
    (Y31D, see TOPUP_WITH_NEW_COMPAT below), +108 pcs.
  - 19 rows are brand-new items for this category (NEW_ITEMS below),
    1,160 pcs. 10,187 + 108 + 1,160 = 11,455 -- reconciles exactly to
    the sheet's own current total.
  - No new damaged/yellow-stock comments this batch (the 5 from the
    2026-09-28 batch are the only ones so far).

Data correction, confirmed with the user (own small step, applied before
the PO so the Realme "C61" reuse below resolves correctly): Model id 283
("RC61") was tagged brand Redmi but is actually a Realme phone -- used by
exactly one item (DPLUG-RC61, Dust Plug category), re-verified fresh
before this script was written. Brand reassigned Redmi -> Realme; name
left as "RC61" (user asked only for the brand fix, not a rename). The
user separately asked for the source Shop Detail.xlsx's Dust Plug sheet
to be corrected too (handled outside this script, since it's their own
file, not production).

Ambiguities resolved with the user, all "/"-separated compatible-model
groups:
  - Vivo "Y31D": the sheet's "Y31D/Y500i (5G)" cell means Y500i (5G) is
    an ADDITIONAL compatible model alongside the item's existing "Y500"
    compatible model (NOT a rename/replacement) -- per the user's
    explicit choice. Existing item 282 (TPU-Y31D) already has Y500 (id
    259) and, unrelated to this sheet, Oppo A61 (id 217) linked; both
    are left untouched, Y500i (5G) is appended.
  - Oppo "Reno 5/F19 Pro": "F19 Pro" confirmed a genuinely distinct phone
    from the catalog's existing plain "F19" model -- created fresh.
  - Realme "Note 60/60X/C61": "C61" reuses Model id 283 (the corrected
    Realme model, not a fresh row) -- resolved explicitly by id below
    since get_or_create_model's name match ("C61" vs the stored "RC61")
    would not have found it otherwise.
  - "Redmi GT/GT Neo": primary "GT", compatible "GT Neo", both new,
    brand Redmi (matches the sheet's own REDMI section header).

Every new/reused model name was cross-checked against the FULL catalog
before deciding brand-new vs reuse (ids re-verified fresh against
production immediately before this script was written):
  OnePlus 8 Pro->482, 8T->194, 7->375, 9 Pro->488, 11->376, 7T->374,
  13->378 (9R and Nord N10 5G are genuinely new).
  Vivo Y18->324, Y03->323, Y20->186 (Y20S/Y12S/Y20i, V70 FE (5G) are new).
  Oppo F11 Pro->99, F11->210, A5->449 (Reno 13F/A3x/Reno 5 Pro/A9/A9X/
  Reno 4 Pro/Reno 11/Reno 5/F19 Pro/F5/A73 are new).
  Realme Note 70->382 (Note 60/Note 60X are new; C61->283, see above).

Run with the backend's own venv (needs the app's DB session/services):
    DATABASE_URL=... backend/.venv/bin/python scripts/import_shop_detail_batch_20261005_tpu.py [--apply]
"""

import argparse
import asyncio
import os
import sys
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend/ on sys.path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

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
TPU_RATE = Decimal("66.04")
CATEGORY_NAME = "TPU Case"
SKU_PREFIX = "TPU"

# --- data correction: Model 283 "RC61" Redmi -> Realme (own small commit) ---
RC61_MODEL_ID = 283
RC61_OLD_BRAND = "Redmi"
RC61_NEW_BRAND = "Realme"

# --- existing item needing a quantity top-up PLUS a new compatible model ---
Y31D_ITEM_ID = 282
Y31D_TOPUP_QTY = Decimal(108)
Y31D_NEW_COMPAT_BRAND = "Vivo"
Y31D_NEW_COMPAT_MODEL = "Y500i (5G)"

# --- brand-new items this batch: (brand, model, [(compat_brand, compat_model), ...], qty) ---
NEW_ITEMS: list[tuple[str, str, list[tuple[str, str]], Decimal]] = [
    ("OnePlus", "8 Pro", [], Decimal(79)),  # reuses existing model id 482
    ("OnePlus", "8T", [], Decimal(56)),  # reuses existing model id 194
    ("OnePlus", "9R", [], Decimal(18)),
    ("OnePlus", "7", [("OnePlus", "6T")], Decimal(31)),  # "7" reuses existing model id 375
    ("OnePlus", "9 Pro", [], Decimal(50)),  # reuses existing model id 488
    ("OnePlus", "11", [], Decimal(72)),  # reuses existing model id 376
    ("OnePlus", "7T", [], Decimal(30)),  # reuses existing model id 374
    ("OnePlus", "Nord N10 5G", [], Decimal(20)),
    ("OnePlus", "13", [], Decimal(17)),  # reuses existing model id 378
    ("Vivo", "V70 FE (5G)", [], Decimal(34)),  # distinct from existing V70/V70 Lite
    ("Vivo", "Y18", [("Vivo", "Y03")], Decimal(95)),  # Y18 reuses id 324, Y03 reuses id 323
    ("Vivo", "Y20", [("Vivo", "Y20S"), ("Vivo", "Y12S"), ("Vivo", "Y20i")], Decimal(63)),  # Y20 reuses id 186
    ("Redmi", "GT", [("Redmi", "GT Neo")], Decimal(28)),
    ("Oppo", "Reno 13F (5G)", [], Decimal(171)),
    ("Oppo", "A3x (4G)(5G)", [], Decimal(46)),
    ("Oppo", "Reno 5 Pro (5G)", [], Decimal(12)),
    ("Oppo", "F11 Pro", [], Decimal(10)),  # reuses existing model id 99
    ("Oppo", "F11", [("Oppo", "A9"), ("Oppo", "A9X")], Decimal(16)),  # F11 reuses id 210
    ("Oppo", "Reno 4 Pro 4G", [], Decimal(22)),
    ("Oppo", "Reno 11", [], Decimal(52)),
    ("Oppo", "Reno 5", [("Oppo", "F19 Pro")], Decimal(46)),  # F19 Pro confirmed distinct from existing F19
    ("Oppo", "F5", [("Oppo", "A73")], Decimal(35)),
]

# Items whose primary model must be reused by EXACT id, not by (brand, name)
# lookup -- the catalog's stored spelling differs from the sheet's own
# wording ("A5" vs sheet's "A5 (4G)"; "REALME NOTE 70" vs sheet's "Note 70"),
# so get_or_create_model's exact-string match would silently create a
# duplicate instead of reusing the row (caught during this script's own dry
# run -- see the two cleaned-up duplicates in the 2026-10-05 conversation).
# (model_id, qty), no compatible models for either.
REUSE_BY_ID_ITEMS: list[tuple[int, Decimal]] = [
    (449, Decimal(42)),  # Oppo "A5" <- sheet's "A5 (4G)"
    (382, Decimal(34)),  # Realme "REALME NOTE 70" <- sheet's "Note 70"
]

# Realme "Note 60/60X/C61": handled separately below since its compatible
# model "C61" must reuse Model id 283 by id (its stored name "RC61" would
# never match a get_or_create_model("Realme", "C61") lookup).
NOTE60_BRAND = "Realme"
NOTE60_MODEL = "Note 60"
NOTE60_COMPAT_NEW = [("Realme", "Note 60X")]
NOTE60_QTY = Decimal(81)


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
    sku = await unique_sku(session, f"{SKU_PREFIX}-{slug(model.name)}")
    row = Item(category_id=category.id, model_id=model.id, sku=sku, variant=None, compatible_models=compatible_models)
    session.add(row)
    await session.flush()
    print(f"Created Item '{sku}' ({model.name}).")
    return row


async def resolve_new_item(session, category: Category, brand_name: str, model_name: str, compat: list[tuple[str, str]]) -> Item:
    brand = await get_or_create_brand(session, brand_name)
    model = await get_or_create_model(session, brand, model_name)
    compat_models = []
    for cbrand, cmodel in compat:
        cb = await get_or_create_brand(session, cbrand)
        cm = await get_or_create_model(session, cb, cmodel)
        compat_models.append(cm)
    return await get_or_create_item(session, category, model, compat_models)


async def main(apply: bool) -> None:
    async with SessionLocal() as session:
        mohsin = await session.scalar(select(Party).where(Party.name == VENDOR_NAME))
        if not mohsin:
            raise RuntimeError(f"Party '{VENDOR_NAME}' not found -- expected to already exist")
        tpu_case = await session.scalar(select(Category).where(Category.name == CATEGORY_NAME))
        if not tpu_case:
            raise RuntimeError(f"Category '{CATEGORY_NAME}' not found -- expected to already exist")

        # --- verify the RC61 model and the Y31D item before touching anything ---
        rc61_model = await session.get(Model, RC61_MODEL_ID)
        if rc61_model is None:
            raise RuntimeError(f"Model {RC61_MODEL_ID} not found -- aborting")
        rc61_old_brand = await session.get(Brand, rc61_model.brand_id)
        if rc61_old_brand.name != RC61_OLD_BRAND:
            raise RuntimeError(
                f"Model {RC61_MODEL_ID} brand is '{rc61_old_brand.name}', expected '{RC61_OLD_BRAND}' -- "
                "state has moved since this script was written, aborting"
            )

        y31d_item = await session.scalar(
            select(Item).options(selectinload(Item.compatible_models)).where(Item.id == Y31D_ITEM_ID)
        )
        if y31d_item is None or y31d_item.category_id != tpu_case.id:
            raise RuntimeError(f"Item {Y31D_ITEM_ID} not found in {CATEGORY_NAME} -- aborting")
        y31d_existing_compat_names = [m.name for m in y31d_item.compatible_models]

        # --- data correction: reassign RC61's brand (gated behind --apply) ---
        realme_brand_for_fix = await get_or_create_brand(session, RC61_NEW_BRAND)
        await session.commit()

        if not apply:
            print(
                f"[DRY RUN] Would reassign Model {RC61_MODEL_ID} ('{rc61_model.name}'): "
                f"{RC61_OLD_BRAND} -> {RC61_NEW_BRAND}"
            )
        else:
            rc61_model.brand_id = realme_brand_for_fix.id
            await session.commit()
            print(f"Reassigned Model {RC61_MODEL_ID} ('{rc61_model.name}'): {RC61_OLD_BRAND} -> {RC61_NEW_BRAND}.")

        # --- resolve every new item's catalog rows (idempotent-safe get-or-create) ---
        new_item_lines: list[tuple[int, Decimal]] = []
        for brand_name, model_name, compat, qty in NEW_ITEMS:
            item = await resolve_new_item(session, tpu_case, brand_name, model_name, compat)
            new_item_lines.append((item.id, qty))

        # --- items whose model must be reused by exact id (see REUSE_BY_ID_ITEMS docstring) ---
        for model_id, qty in REUSE_BY_ID_ITEMS:
            model = await session.get(Model, model_id)
            if model is None:
                raise RuntimeError(f"Model {model_id} not found -- aborting")
            item = await get_or_create_item(session, tpu_case, model, [])
            new_item_lines.append((item.id, qty))

        # --- Note 60/60X/C61: C61 reuses Model 283 explicitly by id ---
        note60_brand = await get_or_create_brand(session, NOTE60_BRAND)
        note60_model = await get_or_create_model(session, note60_brand, NOTE60_MODEL)
        note60_compat_models = [rc61_model]  # C61, reused by id -- name "RC61" would never match by lookup
        for cbrand, cmodel in NOTE60_COMPAT_NEW:
            cb = await get_or_create_brand(session, cbrand)
            cm = await get_or_create_model(session, cb, cmodel)
            note60_compat_models.append(cm)
        note60_item = await get_or_create_item(session, tpu_case, note60_model, note60_compat_models)
        new_item_lines.append((note60_item.id, NOTE60_QTY))
        await session.commit()

        all_lines = [(Y31D_ITEM_ID, Y31D_TOPUP_QTY)] + new_item_lines
        new_total = sum(q for _i, q in new_item_lines)

        if not apply:
            print(f"\n[DRY RUN] {CATEGORY_NAME} PO: {len(all_lines)} lines, total qty {Y31D_TOPUP_QTY + new_total}")
            print(f"[DRY RUN]   Y31D top-up: +{Y31D_TOPUP_QTY} pcs (existing compat models: {y31d_existing_compat_names})")
            print(f"[DRY RUN]   {len(new_item_lines)} new-item lines, {new_total} pcs")
            print(
                f"[DRY RUN] Would add compatible model '{Y31D_NEW_COMPAT_BRAND} {Y31D_NEW_COMPAT_MODEL}' to "
                f"item {Y31D_ITEM_ID} (TPU-Y31D), alongside existing: {y31d_existing_compat_names}"
            )
            print(
                "\nDRY RUN -- catalog rows above were created for real (get-or-create is idempotent-safe on "
                "re-run), but no brand fix, compatible-model addition, purchase order, receipt, or ledger "
                "entry was created. Re-run with --apply to commit."
            )
            return

        # --- Y31D: add the new compatible model (keep existing ones) ---
        y31d_compat_brand = await get_or_create_brand(session, Y31D_NEW_COMPAT_BRAND)
        y31d_compat_model = await get_or_create_model(session, y31d_compat_brand, Y31D_NEW_COMPAT_MODEL)
        y31d_item.compatible_models.append(y31d_compat_model)
        await session.commit()
        print(
            f"Added compatible model '{Y31D_NEW_COMPAT_BRAND} {Y31D_NEW_COMPAT_MODEL}' to item {Y31D_ITEM_ID} "
            f"(TPU-Y31D), alongside existing: {y31d_existing_compat_names}."
        )

        lines_payload = [PurchaseOrderLineCreate(item_id=item_id, qty=qty, rate_pkr=TPU_RATE) for item_id, qty in all_lines]
        po = await purchasing_service.create_purchase_order(
            session, PurchaseOrderCreate(party_id=mohsin.id, order_date=TODAY, source="local", lines=lines_payload)
        )
        print(f"Created PurchaseOrder #{po.id} for '{CATEGORY_NAME}' ({len(lines_payload)} lines).")

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
        print(f"Received all lines, offset Accounts Payable by {po_total} PKR.")

        print(
            f"\nDone. {CATEGORY_NAME}: {Y31D_TOPUP_QTY + new_total} pcs received "
            f"({Y31D_TOPUP_QTY} top-up + {new_total} new), {po_total} PKR."
        )
        print("Accounts Payable to Mohsin offset back to zero.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.apply))
