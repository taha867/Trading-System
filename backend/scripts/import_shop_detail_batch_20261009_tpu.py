"""One-off: the 2026-10-09 Shop Detail update -- more TPU Case stock
received from Mohsin, on top of the 2026-10-05 batch already in
production (script: import_shop_detail_batch_20261005_tpu.py, which
brought TPU Case to 11,455 pcs received).

Reconciliation (sheet grand total now 14,317 pcs, production baseline
before this batch 11,455 pcs, gap 2,862 pcs):
  - 8 existing items get a quantity top-up (TOPUP_ITEMS), 198 pcs; 2 of
    those top-ups also add a brand-new compatible model
    (TOPUP_WITH_COMPAT_ITEMS), 30 pcs -- 228 pcs of top-ups total.
  - 16 items reuse an existing Model row by exact id because the sheet's
    wording doesn't string-match the catalog's stored spelling
    (REUSE_BY_ID_ITEMS -- e.g. sheet "V60 LITE" vs stored "V60 Lite",
    sheet "SPARK 40 PRO+" vs stored "SPARK40PRO+", sheet "NOTE 11 PRO
    (5G)" vs stored "Redmi NOTE11 Pro"), 1,015 pcs.
  - 20 items are brand-new models for this category (NEW_ITEMS), 1,342
    pcs.
  228 + 1,015 + 1,342 = 2,585 pcs applied.

Genuinely ambiguous rows, confirmed NOT to guess, left out of this batch
entirely (277 pcs, not reflected in production -- revisit once the user
clarifies):
  - Vivo "Y15/Y17" (11 pcs) and the separate "Y15" row immediately below
    it (79 pcs, sheet's own comment: "different from Y15/Y17 above (per
    ledger note)"). The catalog already has TWO existing, undistinguished
    "Y15"-family models (plain "Y15" id 181 and "Vivo Y15" id 240) with no
    record of which is which -- creating a third or guessing between the
    two existing ones risks silently misattributing stock to the wrong
    physical phone.
  - Vivo "V40 Lite/Y200/Y300" (137 pcs). The catalog's only near-spelling
    is model id 340, stored as the garbled "V40 Lite (YOUNG" (missing
    closing paren, from an earlier Dust Plug import) -- unclear whether
    this sheet row is that same regional variant or a different one.
  - The "REDMI/VIVO" section header row, "12 (5G)/V60" (50 pcs). This is
    the only row on the whole sheet with a two-brand section header
    (every other section is a single brand), and its own comment flags it
    as a merge of 2 duplicate ledger lines on top of that -- not safe to
    assign to either brand without the user confirming which phone(s) are
    meant.

Also, 3 compatible-model mentions were dropped (brand genuinely
ambiguous -- Vivo has an S-series (S18 already exists in this catalog)
so a bare "S16"/"S17"/"S19 Pro" mentioned alongside Vivo V-series tokens
could be Vivo or Samsung, and no prior-batch precedent disambiguates it).
This does NOT affect any quantity -- only the "also fits" compatible-model
link was skipped, on the items below:
  - Vivo "V27" (new item, 6 pcs): "S16" compatible-model link skipped.
  - Vivo "V40" (reused, +28 pcs... already existing, so this is actually
    a brand-new TPU Case item for the existing "V40" model): "S19 Pro"
    compatible-model link skipped.
  - Vivo "Y29" (reused model, new TPU Case item, 30 pcs): "S17"
    compatible-model link skipped.
Likewise Redmi "12 Pro" (new item, 3 pcs): the sheet's own "12 PRO+"
second token doesn't match any standard Apple/Xiaomi naming convention
(no "iPhone 12 Pro+"/"Redmi 12 Pro+" exists anywhere) -- skipped rather
than guessed.

No new damaged/yellow-stock comments this batch (the only COMMENTS-column
flags on the sheet are the same 5 pieces already handled in the
2026-09-28 batch: iPhone 15 Pro Max, Galaxy S10, A06, Galaxy A13, S8+).

Every new/reused model name was cross-checked against the FULL catalog
(all categories, not just TPU Case) immediately before this script was
written -- ids below are re-verified fresh, not reused from memory:
  Vivo V30->90, V50 Lite->145, Y29S->331 (compat Y04->330), Y31->326,
  V40->92, Y29->336, V50 5G->448, Vivo V60->327, V60 Lite->235, Y55->325,
  Y91->322, A5 Pro->350 (added as a new compat on the existing Oppo A5
  item). Tecno Camon 40->233, Spark 50->305, SPARK40PRO+->460,
  Spark 40 Pro->306. Redmi NOTE11 Pro->381. Oppo A6PRO->351.
  (Y21D, Y95, X70, V9, Y85, Y70, Y27S, S1, Y400, V27, Y36, V20, X80 Pro,
  Reno 11F, Nord N100, Spark 30, Camon 40 Pro, Pova Neo 2, Spark 40, Pop
  Lite, C31, Redmi 12 Pro, Redmi 9C, Redmi 9, Mi Note 12S, C33 4G,
  Note 11 5G are all genuinely new -- confirmed absent from the full
  catalog under any brand/spelling.)

Run with the backend's own venv (needs the app's DB session/services):
    DATABASE_URL=... backend/.venv/bin/python scripts/import_shop_detail_batch_20261009_tpu.py [--apply]
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

# --- existing items needing a plain quantity top-up, no new compatible models ---
# (item_id, qty)
TOPUP_ITEMS: list[tuple[int, Decimal]] = [
    (952, Decimal(30)),  # iPhone 16 Pro Max: 783 -> 813
    (280, Decimal(14)),  # Samsung Galaxy A17: 23 -> 37
    (956, Decimal(1)),  # Samsung S23FE: 69 -> 70
    (286, Decimal(47)),  # Vivo Y19S: 86 -> 133
    (287, Decimal(29)),  # Vivo Y17S: 43 -> 72
    (1052, Decimal(4)),  # Vivo Y20: 63 -> 67 (Y20S/Y12S/Y20i compat already linked)
]

# --- existing items needing a top-up PLUS a brand-new compatible model ---
# (item_id, qty, [compat_model_id, ...])
TOPUP_WITH_COMPAT_ITEMS: list[tuple[int, Decimal, list[int]]] = [
    (994, Decimal(73), [90]),  # Vivo S18: 16 -> 89, + compat Vivo "V30" (id 90)
    (1066, Decimal(30), [350]),  # Oppo A5: 42 -> 72, + compat Oppo "A5 PRO" (id 350)
]

# --- items whose PRIMARY model must be reused by exact id (sheet wording
# doesn't string-match the catalog's stored spelling) -- optional compat
# list per item: ("byid", model_id) reuses another existing model by id,
# ("byname", brand, model) creates/reuses a model by (brand, name) lookup.
# (model_id, qty, compat)
REUSE_BY_ID_ITEMS: list[tuple[int, Decimal, list[tuple]]] = [
    (145, Decimal(152), []),  # Vivo "V50 Lite" (exact spelling, reused for clarity)
    (331, Decimal(11), [("byid", 330)]),  # Vivo "Y29S" <- sheet "Y29S/Y04", + compat Y04 (id 330)
    (326, Decimal(45), [("byname", "Vivo", "Y21D")]),  # Vivo "Y31" <- sheet "Y31(5G)/Y21D"
    (92, Decimal(28), []),  # Vivo "V40" <- sheet "V40(5G)/S19 PRO" (S19 Pro skipped, ambiguous brand)
    (336, Decimal(30), []),  # Vivo "Y29" <- sheet "Y29/S17" (S17 skipped, ambiguous brand)
    (448, Decimal(215), []),  # Vivo "V50 5G" <- sheet "V50(5G)"
    (327, Decimal(76), []),  # Vivo "Vivo V60" <- sheet "V60(5G)"
    (235, Decimal(40), []),  # Vivo "V60 Lite" <- sheet "V60 LITE"
    (325, Decimal(7), []),  # Vivo "Y55" <- sheet "Y55(4G)"
    (322, Decimal(10), [("byname", "Vivo", "Y95"), ("byname", "Vivo", "X70")]),  # Vivo "Y91" <- sheet "Y91/Y95/X70"
    (233, Decimal(110), []),  # Tecno "Camon 40" <- sheet "CAMON 40 4G"
    (305, Decimal(10), []),  # Tecno "Spark 50" <- sheet "SPARK 50 (4G)"
    (460, Decimal(125), []),  # Tecno "SPARK40PRO+" <- sheet "SPARK 40 PRO+"
    (306, Decimal(46), []),  # Tecno "Spark 40 Pro" <- sheet "SPARK 40 PRO"
    (381, Decimal(60), []),  # Redmi "Redmi NOTE11 Pro" <- sheet "NOTE 11 PRO (5G)"
    (351, Decimal(50), []),  # Oppo "A6PRO" <- sheet "A6 PRO"
]

# --- brand-new items this batch: (brand, model, [(compat_brand, compat_model), ...], qty) ---
NEW_ITEMS: list[tuple[str, str, list[tuple[str, str]], Decimal]] = [
    ("Oppo", "Reno 11F", [], Decimal(282)),
    ("OnePlus", "Nord N100", [], Decimal(100)),
    ("Vivo", "V89", [("Vivo", "V9"), ("Vivo", "Y85")], Decimal(51)),
    ("Vivo", "V20SE", [("Vivo", "Y70")], Decimal(23)),
    ("Vivo", "S1", [], Decimal(50)),
    ("Vivo", "Y400", [], Decimal(41)),
    ("Vivo", "V27", [], Decimal(6)),  # "S16" compat skipped, ambiguous brand
    ("Vivo", "Y36", [("Vivo", "Y27S")], Decimal(80)),
    ("Vivo", "V20", [], Decimal(113)),
    ("Vivo", "X80 Pro", [], Decimal(12)),
    ("Tecno", "Spark 30", [], Decimal(63)),
    ("Tecno", "Camon 40 Pro", [], Decimal(15)),
    ("Tecno", "Pova Neo 2", [], Decimal(40)),
    ("Tecno", "Spark 40", [], Decimal(22)),
    ("Tecno", "Pop Lite", [], Decimal(93)),
    ("Redmi", "C31", [], Decimal(100)),
    ("Redmi", "12 Pro", [], Decimal(3)),  # "12 Pro+" compat skipped, not a standard naming
    ("Redmi", "9C", [("Redmi", "9")], Decimal(1)),
    ("Redmi", "Mi Note 12S", [], Decimal(39)),
    ("Redmi", "C33 4G", [], Decimal(144)),
    ("Redmi", "Note 11 5G", [], Decimal(64)),
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


async def resolve_compat(session, compat_spec: list[tuple]) -> list[Model]:
    models = []
    for spec in compat_spec:
        if spec[0] == "byid":
            model = await session.get(Model, spec[1])
            if model is None:
                raise RuntimeError(f"Model {spec[1]} not found -- aborting")
        else:
            _, cbrand, cmodel = spec
            cb = await get_or_create_brand(session, cbrand)
            model = await get_or_create_model(session, cb, cmodel)
        models.append(model)
    return models


async def resolve_new_item(session, category: Category, brand_name: str, model_name: str, compat: list[tuple[str, str]]) -> Item:
    brand = await get_or_create_brand(session, brand_name)
    model = await get_or_create_model(session, brand, model_name)
    compat_models = await resolve_compat(session, [("byname", cb, cm) for cb, cm in compat])
    return await get_or_create_item(session, category, model, compat_models)


async def main(apply: bool) -> None:
    async with SessionLocal() as session:
        mohsin = await session.scalar(select(Party).where(Party.name == VENDOR_NAME))
        if not mohsin:
            raise RuntimeError(f"Party '{VENDOR_NAME}' not found -- expected to already exist")
        tpu_case = await session.scalar(select(Category).where(Category.name == CATEGORY_NAME))
        if not tpu_case:
            raise RuntimeError(f"Category '{CATEGORY_NAME}' not found -- expected to already exist")

        # --- verify every top-up item up front, before creating anything ---
        topup_items = {}
        for item_id, _qty in TOPUP_ITEMS:
            item = await session.get(Item, item_id)
            if item is None or item.category_id != tpu_case.id or not item.is_active:
                raise RuntimeError(f"Item {item_id} not found/active in {CATEGORY_NAME} -- aborting")
            topup_items[item_id] = item

        topup_compat_items = {}
        for item_id, _qty, _compat_ids in TOPUP_WITH_COMPAT_ITEMS:
            item = await session.scalar(
                select(Item).options(selectinload(Item.compatible_models)).where(Item.id == item_id)
            )
            if item is None or item.category_id != tpu_case.id or not item.is_active:
                raise RuntimeError(f"Item {item_id} not found/active in {CATEGORY_NAME} -- aborting")
            topup_compat_items[item_id] = item

        # --- resolve every new item's catalog rows (idempotent-safe get-or-create) ---
        all_lines: list[tuple[int, Decimal]] = []

        for item_id, qty in TOPUP_ITEMS:
            all_lines.append((item_id, qty))

        for item_id, qty, compat_ids in TOPUP_WITH_COMPAT_ITEMS:
            compat_models = await resolve_compat(session, [("byid", mid) for mid in compat_ids])
            item = topup_compat_items[item_id]
            existing_names = [m.name for m in item.compatible_models]
            if not apply:
                print(
                    f"[DRY RUN] Would add compatible model(s) {[m.name for m in compat_models]} to item {item_id} "
                    f"({item.sku}), alongside existing: {existing_names}"
                )
            else:
                for cm in compat_models:
                    item.compatible_models.append(cm)
                print(
                    f"Added compatible model(s) {[m.name for m in compat_models]} to item {item_id} ({item.sku}), "
                    f"alongside existing: {existing_names}."
                )
            all_lines.append((item_id, qty))

        for model_id, qty, compat_spec in REUSE_BY_ID_ITEMS:
            model = await session.get(Model, model_id)
            if model is None:
                raise RuntimeError(f"Model {model_id} not found -- aborting")
            compat_models = await resolve_compat(session, compat_spec)
            item = await get_or_create_item(session, tpu_case, model, compat_models)
            all_lines.append((item.id, qty))

        for brand_name, model_name, compat, qty in NEW_ITEMS:
            item = await resolve_new_item(session, tpu_case, brand_name, model_name, compat)
            all_lines.append((item.id, qty))

        if apply:
            await session.commit()

        new_total = sum(q for _i, q in all_lines)

        if not apply:
            print(f"\n[DRY RUN] {CATEGORY_NAME} PO: {len(all_lines)} lines, total qty {new_total}")
            print(
                "\nDRY RUN -- catalog rows above were created for real (get-or-create is idempotent-safe on "
                "re-run), but no compatible-model addition, purchase order, receipt, or ledger entry was "
                "created. Re-run with --apply to commit."
            )
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

        print(f"\nDone. {CATEGORY_NAME}: {new_total} pcs received, {po_total} PKR.")
        print("Accounts Payable to Mohsin offset back to zero.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.apply))
