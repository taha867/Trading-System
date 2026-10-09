"""One-off: resolves the 3 rows left out of the 2026-10-09 TPU Case batch
(import_shop_detail_batch_20261009_tpu.py) as genuinely ambiguous, now that
the user has clarified each one -- plus one unrelated duplicate-model bug
(SPARK 40 PRO+) found while verifying that batch. Production TPU Case
baseline before this script: 14,040 pcs received.

1. Vivo "Y15/Y17" (11) + the separate "Y15" row (79) -- user: "merge them".
   Investigation found the catalog's two existing "Y15"-family models are
   NOT equally valid duplicates: model 240 "Vivo Y15" has 500 real pcs in
   OG Glass Protector (item 248) but that item's compatible-model links are
   themselves garbled ("iPhone 11"/"iPhone 17" -- clearly wrong for a Vivo
   phone case, a pre-existing unrelated bug). Model 181 "Y15" has zero
   stock (item 199, 0 pcs) but DOES correctly link "Y17" as a compatible
   model. Fix: keep model 240 as canonical, move its *correct* compatible
   model onto it (Y17), strip the wrong iPhone links, retire model 181 and
   its empty item. New TPU Case item: primary "Vivo Y15", compatible "Y17",
   90 pcs (11+79).

2. Vivo "V40 Lite/Y200/Y300" (137) -- user: "/" means compatible models,
   not alternatives; reuse the existing garbled-name model ("merge in it").
   The catalog's model 340 is stored as "V40 Lite (YOUNG" (missing a
   closing paren) with a SINGLE compatible model, 341, stored as "5G30)" --
   together these two clearly show the ORIGINAL sheet cell got split at
   the wrong parenthesis during an earlier Dust Plug import (something like
   "V40 Lite (YOUNG EDITION 5G30)"). Not confident enough in the exact
   intended full name to guess a rename (left as-is per the user's own
   session-wide "don't guess" rule) -- but the compatible-model half,
   "5G30)", is unambiguously garbage (not a real device, referenced
   nowhere else) and is removed. New TPU Case item: primary model 340,
   compatible models "Y200"/"Y300" (both new), 137 pcs.

3. "12 (5G)/V60" (50) -- user: "just add it". Primary: Redmi model 190
   ("12", exact existing spelling, reused). Compatible: Vivo model 327
   ("Vivo V60", added fresh in the 2026-10-09 batch, reused here). New TPU
   Case item, 50 pcs.

4. Tecno "SPARK 40 PRO+" duplicate (found during verification, not from
   the sheet): model 89 is tagged brand Infinix, but Spark is a Tecno
   product line and model 460 ("SPARK40PRO+", no space) is the already-
   correct Tecno model (already used in UV Glass Protector and, via the
   2026-10-09 batch, TPU Case). Model 89's only reference is Dust Plug item
   360 (34 pcs, untouched since receipt) -- no Dust Plug item exists yet
   under model 460, so this is a clean repoint: item 360.model_id 89 -> 460,
   then deactivate model 89. No quantity impact, no new stock.

Expected final TPU Case total: 14,040 + 90 + 137 + 50 = 14,317 -- matching
the sheet's full grand total exactly.

Run with the backend's own venv:
    DATABASE_URL=... backend/.venv/bin/python scripts/fix_tpu_ambiguous_rows_20261009.py [--apply]
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

# --- Fix 1: Y15 ---
Y15_CANONICAL_MODEL_ID = 240  # "Vivo Y15"
Y15_CANONICAL_ITEM_ID = 248  # PROT-VIVOY15 (OG Glass Protector, 500 pcs)
Y15_BOGUS_COMPAT_IDS = [106, 125]  # "iPhone 11", "iPhone 17" -- wrong, removed
Y15_Y17_MODEL_ID = 182  # "Y17" -- correct compat, moved onto the canonical item
Y15_DUPLICATE_ITEM_ID = 199  # PROT-VIVO-Y15-Y17 (0 pcs, retired)
Y15_DUPLICATE_MODEL_ID = 181  # "Y15" (retired)
Y15_TPU_QTY = Decimal(90)  # 11 (Y15/Y17 row) + 79 (second Y15 row)

# --- Fix 2: V40 Lite ---
V40LITE_MODEL_ID = 340  # "V40 Lite (YOUNG" -- left as-is, not confident enough to rename
V40LITE_DUSTPLUG_ITEM_ID = 395  # DPLUG-V40LITEYOUNG
V40LITE_BOGUS_COMPAT_MODEL_ID = 341  # "5G30)" -- garbage, removed
V40LITE_NEW_COMPAT = [("Vivo", "Y200"), ("Vivo", "Y300")]
V40LITE_TPU_QTY = Decimal(137)

# --- Fix 3: 12(5G)/V60 ---
REDMI12_MODEL_ID = 190  # "12"
V60_COMPAT_MODEL_ID = 327  # "Vivo V60"
REDMI12_V60_QTY = Decimal(50)

# --- Fix 4: SPARK 40 PRO+ duplicate (no quantity impact) ---
SPARK40PROPLUS_DUPLICATE_MODEL_ID = 89  # "SPARK 40 PRO+", Infinix (wrong)
SPARK40PROPLUS_CANONICAL_MODEL_ID = 460  # "SPARK40PRO+", Tecno (correct)
SPARK40PROPLUS_DUSTPLUG_ITEM_ID = 360  # DPLUG-SPARK40PRO


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


def slug(text: str) -> str:
    return "".join(c for c in text.upper() if c.isalnum())


async def main(apply: bool) -> None:
    async with SessionLocal() as session:
        mohsin = await session.scalar(select(Party).where(Party.name == VENDOR_NAME))
        if not mohsin:
            raise RuntimeError(f"Party '{VENDOR_NAME}' not found -- expected to already exist")
        tpu_case = await session.scalar(select(Category).where(Category.name == CATEGORY_NAME))
        if not tpu_case:
            raise RuntimeError(f"Category '{CATEGORY_NAME}' not found -- expected to already exist")

        # ---------- verify every target row up front, before touching anything ----------
        y15_item = await session.scalar(
            select(Item).options(selectinload(Item.compatible_models)).where(Item.id == Y15_CANONICAL_ITEM_ID)
        )
        y15_dup_item = await session.get(Item, Y15_DUPLICATE_ITEM_ID)
        y15_dup_model = await session.get(Model, Y15_DUPLICATE_MODEL_ID)
        if y15_item is None or y15_dup_item is None or y15_dup_model is None:
            raise RuntimeError("Y15 fix: expected rows not found -- aborting")
        y15_dup_stock = await session.scalar(
            select(StockLot).where(StockLot.item_id == Y15_DUPLICATE_ITEM_ID)
        )
        if y15_dup_stock is not None:
            raise RuntimeError(f"Y15 fix: item {Y15_DUPLICATE_ITEM_ID} unexpectedly has stock -- aborting")
        y15_current_compat_ids = {m.id for m in y15_item.compatible_models}
        if y15_current_compat_ids != set(Y15_BOGUS_COMPAT_IDS):
            raise RuntimeError(
                f"Y15 fix: item {Y15_CANONICAL_ITEM_ID} compat models are {y15_current_compat_ids}, "
                f"expected exactly {set(Y15_BOGUS_COMPAT_IDS)} -- state has moved, aborting"
            )

        v40lite_item = await session.scalar(
            select(Item).options(selectinload(Item.compatible_models)).where(Item.id == V40LITE_DUSTPLUG_ITEM_ID)
        )
        if v40lite_item is None:
            raise RuntimeError("V40 Lite fix: expected item not found -- aborting")
        v40lite_current_compat_ids = {m.id for m in v40lite_item.compatible_models}
        if v40lite_current_compat_ids != {V40LITE_BOGUS_COMPAT_MODEL_ID}:
            raise RuntimeError(
                f"V40 Lite fix: item {V40LITE_DUSTPLUG_ITEM_ID} compat models are {v40lite_current_compat_ids}, "
                f"expected exactly {{{V40LITE_BOGUS_COMPAT_MODEL_ID}}} -- state has moved, aborting"
            )

        redmi12_model = await session.get(Model, REDMI12_MODEL_ID)
        v60_model = await session.get(Model, V60_COMPAT_MODEL_ID)
        if redmi12_model is None or v60_model is None:
            raise RuntimeError("12(5G)/V60 fix: expected models not found -- aborting")

        spark_dup_model = await session.get(Model, SPARK40PROPLUS_DUPLICATE_MODEL_ID)
        spark_canonical_model = await session.get(Model, SPARK40PROPLUS_CANONICAL_MODEL_ID)
        spark_item = await session.get(Item, SPARK40PROPLUS_DUSTPLUG_ITEM_ID)
        if spark_dup_model is None or spark_canonical_model is None or spark_item is None:
            raise RuntimeError("SPARK 40 PRO+ fix: expected rows not found -- aborting")
        if spark_item.model_id != SPARK40PROPLUS_DUPLICATE_MODEL_ID:
            raise RuntimeError(
                f"SPARK 40 PRO+ fix: item {SPARK40PROPLUS_DUSTPLUG_ITEM_ID} model_id is "
                f"{spark_item.model_id}, expected {SPARK40PROPLUS_DUPLICATE_MODEL_ID} -- state has moved, aborting"
            )
        existing_canonical_dustplug_item = await session.scalar(
            select(Item).where(
                Item.category_id == spark_item.category_id,
                Item.model_id == SPARK40PROPLUS_CANONICAL_MODEL_ID,
            )
        )
        if existing_canonical_dustplug_item is not None:
            raise RuntimeError(
                "SPARK 40 PRO+ fix: a Dust Plug item already exists under the canonical model -- "
                "needs a stock merge, not a simple repoint. Aborting."
            )

        if not apply:
            print("[DRY RUN] Fix 1 (Y15): remove compat", Y15_BOGUS_COMPAT_IDS, f"from item {Y15_CANONICAL_ITEM_ID}; "
                  f"add compat Y17 (id {Y15_Y17_MODEL_ID}); deactivate item {Y15_DUPLICATE_ITEM_ID} and "
                  f"model {Y15_DUPLICATE_MODEL_ID}; new TPU item for model {Y15_CANONICAL_MODEL_ID}, {Y15_TPU_QTY} pcs")
            print(f"[DRY RUN] Fix 2 (V40 Lite): remove compat model {V40LITE_BOGUS_COMPAT_MODEL_ID} from item "
                  f"{V40LITE_DUSTPLUG_ITEM_ID}; deactivate it; new TPU item for model {V40LITE_MODEL_ID} with "
                  f"compat {V40LITE_NEW_COMPAT}, {V40LITE_TPU_QTY} pcs")
            print(f"[DRY RUN] Fix 3 (12/V60): new TPU item, primary model {REDMI12_MODEL_ID}, "
                  f"compat model {V60_COMPAT_MODEL_ID}, {REDMI12_V60_QTY} pcs")
            print(f"[DRY RUN] Fix 4 (SPARK 40 PRO+): repoint item {SPARK40PROPLUS_DUSTPLUG_ITEM_ID} from model "
                  f"{SPARK40PROPLUS_DUPLICATE_MODEL_ID} -> {SPARK40PROPLUS_CANONICAL_MODEL_ID}; deactivate model "
                  f"{SPARK40PROPLUS_DUPLICATE_MODEL_ID} (no quantity impact)")
            print("\nDRY RUN -- nothing written. Re-run with --apply to commit.")
            return

        # ---------- Fix 1: Y15 ----------
        y15_item.compatible_models = [m for m in y15_item.compatible_models if m.id not in Y15_BOGUS_COMPAT_IDS]
        y17_model = await session.get(Model, Y15_Y17_MODEL_ID)
        y15_item.compatible_models.append(y17_model)
        y15_dup_item.is_active = False
        y15_dup_model.is_active = False
        print(f"Fix 1: item {Y15_CANONICAL_ITEM_ID} compat models corrected to [Y17]; "
              f"item {Y15_DUPLICATE_ITEM_ID} and model {Y15_DUPLICATE_MODEL_ID} deactivated.")

        # ---------- Fix 2: V40 Lite ----------
        v40lite_item.compatible_models = [
            m for m in v40lite_item.compatible_models if m.id != V40LITE_BOGUS_COMPAT_MODEL_ID
        ]
        bogus_compat_model = await session.get(Model, V40LITE_BOGUS_COMPAT_MODEL_ID)
        bogus_compat_model.is_active = False
        print(f"Fix 2: removed bogus compat model {V40LITE_BOGUS_COMPAT_MODEL_ID} from item "
              f"{V40LITE_DUSTPLUG_ITEM_ID}; deactivated it.")

        # ---------- Fix 4: SPARK 40 PRO+ (repoint before committing catalog changes) ----------
        spark_item.model_id = SPARK40PROPLUS_CANONICAL_MODEL_ID
        spark_dup_model.is_active = False
        print(f"Fix 4: item {SPARK40PROPLUS_DUSTPLUG_ITEM_ID} repointed to model "
              f"{SPARK40PROPLUS_CANONICAL_MODEL_ID}; model {SPARK40PROPLUS_DUPLICATE_MODEL_ID} deactivated.")

        await session.commit()

        # ---------- resolve the 3 new TPU Case lines ----------
        y15_model = await session.get(Model, Y15_CANONICAL_MODEL_ID)
        y15_tpu_item = await get_or_create_item(session, tpu_case, y15_model, [y17_model])

        v40lite_model = await session.get(Model, V40LITE_MODEL_ID)
        v40lite_new_compat_models = []
        for cbrand, cmodel in V40LITE_NEW_COMPAT:
            cb = await get_or_create_brand(session, cbrand)
            cm = await get_or_create_model(session, cb, cmodel)
            v40lite_new_compat_models.append(cm)
        v40lite_tpu_item = await get_or_create_item(session, tpu_case, v40lite_model, v40lite_new_compat_models)

        redmi12_tpu_item = await get_or_create_item(session, tpu_case, redmi12_model, [v60_model])

        await session.commit()

        lines = [
            (y15_tpu_item.id, Y15_TPU_QTY),
            (v40lite_tpu_item.id, V40LITE_TPU_QTY),
            (redmi12_tpu_item.id, REDMI12_V60_QTY),
        ]
        lines_payload = [PurchaseOrderLineCreate(item_id=item_id, qty=qty, rate_pkr=TPU_RATE) for item_id, qty in lines]
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

        new_total = sum(q for _i, q in lines)
        print(f"\nDone. {CATEGORY_NAME}: {new_total} pcs received across the 3 resolved rows, {po_total} PKR.")
        print("Accounts Payable to Mohsin offset back to zero.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.apply))
