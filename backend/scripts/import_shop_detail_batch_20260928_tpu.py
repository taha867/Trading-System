"""One-off: the 2026-09-28 Shop Detail update -- TPU Case stock received
from Mohsin. Confirmed with the user after a full row-by-row reconciliation
of the TPU sheet against production (see the 2026-09-28 conversation).

Summary of the reconciliation (134 sheet rows, sheet grand total 8,817 pcs,
production baseline before this batch 1,476 pcs across 48 items):
  - 26 rows already matched production exactly -- no action.
  - 22 existing items get a quantity top-up (TOPUPS below), total +1,738 pcs.
  - 86 rows are brand-new items for this category (NEW_ITEMS below), total
    5,603 pcs. 1,476 + 1,738 + 5,603 = 8,817 -- reconciles exactly to the
    sheet's own total, confirming every row is accounted for exactly once.

Two data corrections, confirmed with the user, applied before the PO (their
own small commits, no quantity impact -- the sheet's own quantities for
these rows already matched production exactly once you see past the typo):
  - Vivo Model "F1 PRO" was a typo for "F11 Pro" (the sheet's own "F11 PRO"
    row is 51 pcs, exactly matching production's "F1 PRO" item) -- renamed
    in place, not treated as new stock.
  - Model "Y31D" was tagged brand Oppo but the sheet lists it under Vivo,
    and its qty already matched exactly (9=9) -- brand_id reassigned to
    Vivo, not treated as new stock.

Ambiguities resolved with the user, all "/"-separated compatible-model
pairs (primary item's own StockLot covers both models' physical stock):
  - "13/14" (existing item 268, iPhone 13) already had "iPhone 14" linked
    as a compatible model from a prior import, with quantity already
    matching exactly (16=16) -- fully pre-reconciled, not touched here.
  - "7+/8+" (existing item 275, iPhone 7+) already had "iPhone 8+" linked;
    only the quantity top-up is new here.
  - "50/55" (existing item 276, iPhone 50) already had "iPhone 55" linked,
    quantity already matching exactly (20=20) -- fully pre-reconciled.
  - "Y90/Y91C", "Y31D/Y500", "Y05/Y110", "VIVO V70/V70 LITE" (existing
    items 281/282/283/284) already had their compatible models linked,
    quantities already matching exactly -- fully pre-reconciled.
  - "HOT 60/60i" (existing item 305) already had "60i" linked; only the
    quantity top-up is new here.
  - "NOTE 60/60 PRO" (existing item 306): quantity top-up applied, but its
    existing compatible-model link is "iPhone 60 Pro" -- clearly a
    pre-existing data-entry bug (an Infinix case linked to an iPhone
    model), unrelated to this batch. NOT fixed here -- flagged for the
    user to confirm the correct link ("Note 60 Pro") separately.
  - New compatible-model pairs created fresh this batch: iPhone
    6/6s/7/8 (primary iPhone 7), iPhone 12/12 Pro, iPhone 13 Pro Max/12
    Pro Max, iPhone 5/5s/SE (primary iPhone 5s), Galaxy A14/A14 5G
    (primary reuses the existing plain "Galaxy A14"), Galaxy S10/J5
    (primary Galaxy S10 -- also the row with a damaged-stock split, see
    below), Samsung J7/J7 Core (primary reuses the existing "J7"),
    Infinix Hot 10 Play/Hot 11 Play (deliberately NOT reusing the
    catalog's existing dirty "10 PLAY" model -- that's a leftover
    prefix-stripped duplicate from an older import; a clean "Hot 10 Play"
    is created instead, matching how "Hot 12 Play" is already spelled).

Every new model name below was cross-checked against the FULL catalog
(every category, not just TPU Case) before deciding brand-new vs reuse, to
avoid adding fresh spelling-duplicates on top of this catalog's existing
debt (dozens of pre-existing near-duplicate Samsung/Redmi/Vivo model names
were found during this check -- not this batch's problem to clean up, but
worth reusing an exact existing spelling wherever one exists).

Damaged/yellow stock: the sheet's COMMENTS column (a plain column, not an
Excel cell-note) flagged 5 rows as partially or fully damaged. All 5 are
brand-new items this batch, so the full sheet quantity is received first,
then the damaged portion is immediately marked via mark_stock_lot_damaged,
leaving qty_remaining at the "normal" portion:
  - iPhone 15 Pro Max: 125 received -> 5 damaged, 120 sellable.
  - Galaxy S10 (the S10/J5 compatible pair): 93 received -> 10 damaged, 83 sellable.
  - A06: 11 received -> 10 damaged, 1 sellable.
  - Galaxy A13: 35 received -> 35 damaged, 0 sellable (100% damaged, confirmed with the user).
  - S8+: 7 received -> 5 damaged, 2 sellable.

Run with the backend's own venv (needs the app's DB session/services):
    DATABASE_URL=... backend/.venv/bin/python scripts/import_shop_detail_batch_20260928_tpu.py [--apply]
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
TPU_RATE = Decimal("66.04")
CATEGORY_NAME = "TPU Case"
SKU_PREFIX = "TPU"

# --- data corrections (own commits, no quantity impact) ---
RENAME_MODEL = ("Vivo", "F1 PRO", "F11 Pro")  # (brand, old_name, new_name)
BRAND_FIX_MODEL = ("Y31D", "Oppo", "Vivo")  # (model_name, old_brand, new_brand)

# --- existing items needing a quantity top-up: (item_id, qty_added) ---
TOPUPS: list[tuple[int, Decimal]] = [
    (263, Decimal(56)),   # iPhone X 11->67
    (264, Decimal(23)),   # iPhone XR 31->54
    (266, Decimal(34)),   # iPhone 11 28->62
    (269, Decimal(63)),   # iPhone 13 Pro 21->84
    (270, Decimal(150)),  # iPhone 14 Pro 17->167
    (271, Decimal(120)),  # iPhone 17 19->139
    (272, Decimal(125)),  # iPhone 17 Air 20->145
    (273, Decimal(124)),  # iPhone 17 Pro 14->138
    (274, Decimal(81)),   # iPhone 17 Pro Max 20->101
    (275, Decimal(122)),  # iPhone 7+ 23->145 (compat iPhone 8+ already linked)
    (279, Decimal(27)),   # Galaxy A32 10->37
    (280, Decimal(15)),   # Galaxy A17 8->23
    (289, Decimal(58)),   # Pixel 6A 21->79
    (291, Decimal(96)),   # Pixel 7A 14->110
    (292, Decimal(40)),   # Pixel 8 21->61
    (293, Decimal(119)),  # Pixel 9 23->142
    (294, Decimal(34)),   # Pixel 9 Pro XL 40->74
    (302, Decimal(153)),  # Infinix NOTE EDGE 19->172
    (304, Decimal(32)),   # Infinix HOT 60 PRO+ 21->53
    (305, Decimal(78)),   # Infinix HOT 60 21->99 (compat 60i already linked)
    (306, Decimal(72)),   # Infinix Note 60 9->81 (compat link bug NOT fixed here, see docstring)
    (310, Decimal(116)),  # Redmi C85 36->152
]

# --- brand-new items this batch: (brand, model, [(compat_brand, compat_model), ...], qty) ---
NEW_ITEMS: list[tuple[str, str, list[tuple[str, str]], Decimal]] = [
    ("iPhone", "iPhone 7", [("iPhone", "iPhone 6"), ("iPhone", "iPhone 6S"), ("iPhone", "iPhone 8")], Decimal(22)),
    ("iPhone", "iPhone 13 mini", [], Decimal(57)),
    ("iPhone", "iPhone 13 Pro Max", [("iPhone", "iPhone 12 Pro Max")], Decimal(88)),
    ("iPhone", "iPhone 5s", [("iPhone", "iPhone 5"), ("iPhone", "iPhone SE")], Decimal(50)),
    ("iPhone", "iPhone 15 Pro", [], Decimal(164)),
    ("iPhone", "iPhone 15 Pro Max", [], Decimal(125)),  # damaged split: 120 normal / 5 damaged
    ("iPhone", "iPhone 15+", [], Decimal(57)),
    ("iPhone", "iPhone 16+", [], Decimal(62)),
    ("iPhone", "iPhone 16 Pro", [], Decimal(418)),
    ("iPhone", "iPhone 16 Pro Max", [], Decimal(783)),
    ("iPhone", "iPhone 12", [("iPhone", "iPhone 12 Pro")], Decimal(32)),
    ("Samsung", "S23 ULTRA", [], Decimal(1)),
    ("Samsung", "Galaxy A14", [("Samsung", "Galaxy A14 5G")], Decimal(153)),
    ("Samsung", "S23 Fe", [], Decimal(69)),
    ("Samsung", "Galaxy S20 FE", [], Decimal(76)),
    ("Samsung", "Galaxy S10", [("Samsung", "J5")], Decimal(93)),  # damaged split: 83 normal / 10 damaged
    ("Samsung", "Galaxy A04e", [], Decimal(103)),
    ("Samsung", "J7", [("Samsung", "J7 Core")], Decimal(15)),
    ("Samsung", "Galaxy A53 5G", [], Decimal(10)),
    ("Samsung", "Galaxy A16", [], Decimal(131)),
    ("Samsung", "Galaxy A26", [], Decimal(70)),
    ("Samsung", "S7", [], Decimal(15)),
    ("Samsung", "A06", [], Decimal(11)),  # damaged split: 1 normal / 10 damaged
    ("Samsung", "Galaxy S22+", [], Decimal(33)),
    ("Samsung", "Galaxy S24", [], Decimal(43)),
    ("Samsung", "Galaxy S21 FE", [], Decimal(47)),
    ("Samsung", "Galaxy A81", [], Decimal(32)),
    ("Samsung", "Galaxy S20 Ultra", [], Decimal(73)),
    ("Samsung", "Galaxy A6+", [("Samsung", "J8")], Decimal(29)),
    ("Samsung", "Galaxy A05s", [], Decimal(17)),
    ("Samsung", "Galaxy S20", [], Decimal(25)),
    ("Samsung", "Note 8", [], Decimal(24)),
    ("Samsung", "S20+", [], Decimal(10)),
    ("Samsung", "Galaxy A96", [], Decimal(10)),
    ("Samsung", "J700", [], Decimal(10)),
    ("Samsung", "J530", [], Decimal(3)),
    ("Samsung", "Galaxy A03s", [], Decimal(203)),
    ("Samsung", "Galaxy S25+", [], Decimal(76)),
    ("Samsung", "Galaxy S25", [], Decimal(46)),
    ("Samsung", "Galaxy S24 Ultra", [], Decimal(10)),
    ("Samsung", "Galaxy S25 Edge", [], Decimal(85)),
    ("Samsung", "J2 Pro", [], Decimal(18)),
    ("Samsung", "Note 10", [], Decimal(77)),
    ("Samsung", "J500", [], Decimal(32)),
    ("Samsung", "J2 Prime", [], Decimal(21)),
    ("Samsung", "Galaxy A31", [], Decimal(18)),
    ("Samsung", "Galaxy A20s", [], Decimal(20)),
    ("Samsung", "Galaxy A13", [], Decimal(35)),  # damaged split: 0 normal / 35 damaged (100%, confirmed)
    ("Samsung", "S8+", [], Decimal(7)),  # damaged split: 2 normal / 5 damaged
    ("Samsung", "S9", [], Decimal(11)),
    ("Samsung", "Note 20", [], Decimal(50)),
    ("Vivo", "S18", [], Decimal(16)),
    ("Vivo", "V30E", [], Decimal(13)),
    ("Google Pixel", "Pixel 10", [], Decimal(10)),
    ("Infinix", "Smart 5", [], Decimal(18)),
    ("Infinix", "Smart 10", [], Decimal(88)),
    ("Infinix", "Smart 10 Plus", [], Decimal(73)),
    ("Infinix", "Smart 6", [], Decimal(140)),
    ("Infinix", "HOT 60 PRO", [], Decimal(30)),
    ("Infinix", "NOTE8", [], Decimal(39)),
    ("Infinix", "Note 8i", [], Decimal(31)),
    ("Infinix", "Note 7", [], Decimal(21)),
    ("Infinix", "Hot 10S", [], Decimal(30)),
    ("Infinix", "Hot 50 Pro", [], Decimal(60)),
    ("Infinix", "Hot 20i", [], Decimal(120)),
    ("Infinix", "Hot 40", [], Decimal(50)),
    ("Infinix", "Hot 10 Play", [("Infinix", "Hot 11 Play")], Decimal(55)),
    ("Infinix", "Hot 50I", [], Decimal(29)),
    ("Infinix", "HOT 50 PRO+", [], Decimal(52)),
    ("Infinix", "Hot 50", [], Decimal(17)),
    ("Infinix", "Hot 10 Lite", [], Decimal(45)),
    ("Infinix", "Hot 70", [], Decimal(40)),
    ("Itel", "S25 Ultra", [], Decimal(49)),
    ("Itel", "A100C", [], Decimal(64)),
    ("Redmi", "Mi A3 4G", [], Decimal(111)),
    ("Redmi", "13C", [], Decimal(52)),
    ("Redmi", "14T (5G)", [], Decimal(19)),
    ("Redmi", "Note 10 Lite", [], Decimal(49)),
    ("Redmi", "Note 10 Pro 5G", [], Decimal(38)),
    ("Redmi", "Note 14 Pro", [], Decimal(124)),
    ("Redmi", "Note 14", [], Decimal(104)),
    ("Redmi", "Note 14 Pro+", [], Decimal(168)),
    ("Redmi", "10C", [], Decimal(56)),
    ("Oppo", "Reno Z", [], Decimal(10)),
    ("Realme", "RM15 (5G)", [], Decimal(52)),
    ("Realme", "RM15C (4G)", [], Decimal(60)),
]

# model name -> (damaged_qty, reason) -- applied after receiving the full qty above
DAMAGED_SPLITS: dict[str, tuple[Decimal, str]] = {
    "iPhone 15 Pro Max": (Decimal(5), "5 pcs yellow/damaged, noted in the 2026-09-28 TPU Case sheet update"),
    "Galaxy S10": (Decimal(10), "10 pcs yellow/damaged, noted in the 2026-09-28 TPU Case sheet update"),
    "A06": (Decimal(10), "10 pcs yellow/damaged, noted in the 2026-09-28 TPU Case sheet update"),
    "Galaxy A13": (Decimal(35), "35 pcs yellow/damaged (100% of this lot), noted in the 2026-09-28 TPU Case sheet update"),
    "S8+": (Decimal(5), "5 pcs yellow/damaged, noted in the 2026-09-28 TPU Case sheet update"),
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

        # --- data corrections (own small commits, no quantity impact) ---
        rename_brand_name, old_name, new_name = RENAME_MODEL
        rename_brand = await session.scalar(select(Brand).where(Brand.name == rename_brand_name))
        rename_model = await session.scalar(
            select(Model).where(Model.brand_id == rename_brand.id, Model.name == old_name)
        )
        if rename_model is None:
            raise RuntimeError(f"Model '{rename_brand_name} {old_name}' not found -- aborting")

        fix_model_name, old_brand_name, new_brand_name = BRAND_FIX_MODEL
        old_brand = await session.scalar(select(Brand).where(Brand.name == old_brand_name))
        fix_model = await session.scalar(
            select(Model).where(Model.brand_id == old_brand.id, Model.name == fix_model_name)
        )
        if fix_model is None:
            raise RuntimeError(f"Model '{old_brand_name} {fix_model_name}' not found -- aborting")
        new_brand = await get_or_create_brand(session, new_brand_name)
        await session.commit()

        # --- resolve every new item's catalog rows (idempotent-safe get-or-create) ---
        new_item_lines: list[tuple[int, Decimal]] = []
        new_item_by_model_name: dict[str, Item] = {}
        for brand_name, model_name, compat, qty in NEW_ITEMS:
            item = await resolve_new_item(session, tpu_case, brand_name, model_name, compat)
            new_item_lines.append((item.id, qty))
            new_item_by_model_name[model_name] = item
        await session.commit()

        all_lines = TOPUPS + new_item_lines
        topup_total = sum(q for _i, q in TOPUPS)
        new_total = sum(q for _i, q in new_item_lines)

        if not apply:
            print(f"\n[DRY RUN] {CATEGORY_NAME} PO: {len(all_lines)} lines, total qty {topup_total + new_total}")
            print(f"[DRY RUN]   {len(TOPUPS)} top-up lines, +{topup_total} pcs")
            print(f"[DRY RUN]   {len(NEW_ITEMS)} new-item lines, {new_total} pcs")
            print(f"[DRY RUN] Rename pending: {rename_brand_name} '{old_name}' (id {rename_model.id}) -> '{new_name}'")
            print(
                f"[DRY RUN] Brand fix pending: Model '{fix_model_name}' (id {fix_model.id}) "
                f"{old_brand_name} -> {new_brand_name}"
            )
            print(f"[DRY RUN] Damaged splits pending for: {list(DAMAGED_SPLITS.keys())}")
            print(
                "\nDRY RUN -- catalog rows above were created for real (get-or-create is idempotent-safe on "
                "re-run), but no rename/brand-fix, purchase order, receipt, ledger entry, or damaged-stock "
                "movement was created. Re-run with --apply to commit."
            )
            return

        rename_model.name = new_name
        print(f"Renamed {rename_brand_name} Model {rename_model.id}: '{old_name}' -> '{new_name}'.")
        fix_model.brand_id = new_brand.id
        print(f"Reassigned Model {fix_model.id} '{fix_model_name}': {old_brand_name} -> {new_brand_name}.")
        await session.commit()

        lines_payload = [PurchaseOrderLineCreate(item_id=item_id, qty=qty, rate_pkr=TPU_RATE) for item_id, qty in all_lines]
        po = await purchasing_service.create_purchase_order(
            session, PurchaseOrderCreate(party_id=mohsin.id, order_date=TODAY, source="local", lines=lines_payload)
        )
        print(f"Created PurchaseOrder #{po.id} for '{CATEGORY_NAME}' ({len(lines_payload)} lines).")

        lots_by_item_id: dict[int, StockLot] = {}
        po_total = Decimal(0)
        for line in po.lines:
            lot = await inventory_service.receive_purchase_order_line(
                session, StockLotReceiveCreate(purchase_order_line_id=line.id, received_date=TODAY)
            )
            lots_by_item_id[line.item_id] = lot
            po_total += money(lot.qty_received * lot.landed_cost_pkr)
        po_total = money(po_total)

        await ledger_service.post_entry(
            session, entry_date=TODAY, account="Accounts Payable", debit=po_total,
            reference_type="purchase_order", reference_id=po.id, party_id=mohsin.id,
        )
        await session.commit()
        print(f"Received all lines, offset Accounts Payable by {po_total} PKR.")

        for model_name, (damaged_qty, reason) in DAMAGED_SPLITS.items():
            item = new_item_by_model_name[model_name]
            lot = lots_by_item_id[item.id]
            await inventory_service.mark_stock_lot_damaged(
                session, StockLotDamageCreate(stock_lot_id=lot.id, qty=damaged_qty, reason=reason, movement_date=TODAY)
            )
            print(f"  Marked {damaged_qty} pcs damaged on lot {lot.id} ({model_name}).")
        await session.commit()

        print(f"\nDone. {CATEGORY_NAME}: {topup_total + new_total} pcs received ({topup_total} top-up + {new_total} new), {po_total} PKR.")
        print("Accounts Payable to Mohsin offset back to zero.")
        print(
            "Not fixed (flagged for the user): item 306 (Infinix Note 60)'s existing compatible-model link "
            "is 'iPhone 60 Pro' -- almost certainly should be 'Note 60 Pro', a pre-existing data bug unrelated "
            "to this batch."
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.apply))
