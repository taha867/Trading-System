"""One-off: the 2026-10-01 Shop Detail update -- more TPU Case stock
received from Mohsin, on top of the 2026-09-28 batch already in
production (script: import_shop_detail_batch_20260928_tpu.py, which
brought TPU Case to 8,817 pcs received / 8,752 sellable). Confirmed with
the user after a fresh row-by-row reconciliation of the TPU sheet against
production (see the 2026-10-01 conversation).

Summary of the reconciliation (sheet grand total now 10,187 pcs,
production baseline before this batch 8,817 pcs):
  - 124 rows already matched production exactly -- no action.
  - 3 existing items get a quantity top-up (TOPUPS below), total +171 pcs.
  - 12 rows are brand-new items for this category (NEW_ITEMS below), total
    1,199 pcs. 8,817 + 171 + 1,199 = 10,187 -- reconciles exactly to the
    sheet's own current total.
  - No new damaged/yellow-stock comments this batch (the 5 from the
    2026-09-28 batch are the only ones so far) -- no damaged-stock
    splitting needed here.

Ambiguities resolved with the user, all "/"-separated compatible-model
groups:
  - "C51/C53" (Realme section) -> primary Realme C51, compatible Realme
    C53. NOTE: a Model named "C51" already exists in the catalog (id 220)
    but it's tagged brand Redmi, used by 3 active items across OG Glass
    Protector/Polish Glass Protector/Simple Privacy Protector -- almost
    certainly a pre-existing brand mis-tag (Realme C51 mis-filed as
    Redmi), unrelated to this batch and NOT fixed here. A fresh, correctly
    -branded "C51" Model is created under Realme instead of reusing/fixing
    that row -- flagged for the user to decide separately whether to
    rename that brand later (same conservative pattern as leaving item
    306's bad compatible-model link alone in the prior batch).
  - "K40 PRO/K40/11i" (Redmi section) -> primary Redmi K40 Pro, compatible
    Redmi K40 and Redmi 11i. All three are new to the catalog.
  - "NOTE 9/10X" (Redmi section) -> primary Redmi Note 9, compatible Redmi
    Note 10X. Both new to the catalog.

Every new/reused model name was cross-checked against the FULL catalog
(every category, not just TPU Case) to avoid fresh spelling-duplicates:
  - "Reno 13" (sheet cell "RENO 13 (5G)") reuses the existing Oppo "Reno
    13" (id 192, used elsewhere e.g. OG Glass Protector).
  - "Reno 2" reuses the existing Oppo "Reno 2" (id 397, used in Polish
    Glass Protector).
  - "12C" reuses the existing Redmi "12C" (id 228).
  - "14C" (sheet cell "14C 4G") reuses the existing Redmi "14C" (id 226,
    used in several categories) -- the sheet's "4G" is redundant (Redmi
    14C is a 4G-only phone in reality), not a distinct variant.
  - "13 4G", "Note 13", "Note 13 Pro 5G", "Note 15 Pro 5G", "K40 Pro/K40/
    11i", "Note 9/Note 10X" have no existing match anywhere in the
    catalog under Redmi -- created fresh.
  - "14T Pro 5G" under Realme is genuinely distinct from Redmi's own
    existing "14T (5G)" (id 536) -- different brand and different model
    (Pro vs non-Pro) -- created fresh under Realme, not reused.

Run with the backend's own venv (needs the app's DB session/services):
    DATABASE_URL=... backend/.venv/bin/python scripts/import_shop_detail_batch_20261001_tpu.py [--apply]
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
TPU_RATE = Decimal("66.04")
CATEGORY_NAME = "TPU Case"
SKU_PREFIX = "TPU"

# --- existing items needing a quantity top-up: (item_id, qty_added) ---
TOPUPS: list[tuple[int, Decimal]] = [
    (309, Decimal(116)),  # Redmi 15C 68->184
    (981, Decimal(22)),   # Samsung Galaxy S25 46->68
    (1026, Decimal(33)),  # Oppo Reno Z 10->43
]

# --- brand-new items this batch: (brand, model, [(compat_brand, compat_model), ...], qty) ---
NEW_ITEMS: list[tuple[str, str, list[tuple[str, str]], Decimal]] = [
    ("Redmi", "12C", [], Decimal(478)),  # reuses existing model id 228
    ("Redmi", "Note 13 Pro 5G", [], Decimal(150)),
    ("Oppo", "Reno 13", [], Decimal(110)),  # reuses existing model id 192
    ("Redmi", "Note 13", [], Decimal(100)),
    ("Realme", "C51", [("Realme", "C53")], Decimal(82)),  # fresh row, see docstring re: mis-tagged Redmi "C51"
    ("Redmi", "14C", [], Decimal(76)),  # reuses existing model id 226 ("14C 4G" on the sheet, redundant "4G")
    ("Redmi", "K40 Pro", [("Redmi", "K40"), ("Redmi", "11i")], Decimal(48)),
    ("Redmi", "13 4G", [], Decimal(43)),
    ("Oppo", "Reno 2", [], Decimal(32)),  # reuses existing model id 397
    ("Realme", "14T Pro 5G", [], Decimal(29)),
    ("Redmi", "Note 15 Pro 5G", [], Decimal(27)),
    ("Redmi", "Note 9", [("Redmi", "Note 10X")], Decimal(24)),
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

        # --- verify top-up targets exist before touching anything ---
        for item_id, _qty in TOPUPS:
            item = await session.get(Item, item_id)
            if item is None or item.category_id != tpu_case.id:
                raise RuntimeError(f"Item {item_id} not found in {CATEGORY_NAME} -- aborting")

        # --- resolve every new item's catalog rows (idempotent-safe get-or-create) ---
        new_item_lines: list[tuple[int, Decimal]] = []
        for brand_name, model_name, compat, qty in NEW_ITEMS:
            item = await resolve_new_item(session, tpu_case, brand_name, model_name, compat)
            new_item_lines.append((item.id, qty))
        await session.commit()

        all_lines = TOPUPS + new_item_lines
        topup_total = sum(q for _i, q in TOPUPS)
        new_total = sum(q for _i, q in new_item_lines)

        if not apply:
            print(f"\n[DRY RUN] {CATEGORY_NAME} PO: {len(all_lines)} lines, total qty {topup_total + new_total}")
            print(f"[DRY RUN]   {len(TOPUPS)} top-up lines, +{topup_total} pcs")
            print(f"[DRY RUN]   {len(NEW_ITEMS)} new-item lines, {new_total} pcs")
            print("\nDRY RUN -- catalog rows above were created for real (get-or-create is idempotent-safe on "
                  "re-run), but no purchase order, receipt, or ledger entry was created. Re-run with --apply to commit.")
            return

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

        print(f"\nDone. {CATEGORY_NAME}: {topup_total + new_total} pcs received ({topup_total} top-up + {new_total} new), {po_total} PKR.")
        print("Accounts Payable to Mohsin offset back to zero.")
        print(
            "Not fixed (flagged for the user): Model 'C51' (id 220, brand Redmi) is almost certainly a "
            "mis-tagged Realme C51 -- used by 3 active items (OG Glass Protector, Polish Glass Protector, "
            "Simple Privacy Protector). A fresh, correctly-branded Realme 'C51' was created for this batch "
            "instead of reusing/fixing that row."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.apply))
