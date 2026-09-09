"""Phase 2 (writes to the database): import Shop Detail.xlsx received stock.

Reads the reviewed CSV from Phase 1 (shop_detail_preview.py) and, per row_id
group (one PurchaseOrderLine per original sheet row, not per split token):
  1. get-or-creates Category/Brand/Model/Item rows needed
  2. creates one PurchaseOrder per category (source="local", vendor=Mohsin)
  3. receives every line into a StockLot (posts the normal Inventory debit)
  4. posts an offsetting Accounts Payable debit so the net payable to Mohsin
     stays at zero -- this stock is Shakeel's own already-settled share of
     the partnership split, not a real outstanding debt (confirmed with the
     user).

Run with the backend's own venv (needs the app's DB session/services), not
the scratch xlsx venv:
    DATABASE_URL=... backend/.venv/bin/python scripts/import_shop_detail.py
"""

import asyncio
import csv
import os
import sys
from collections import defaultdict
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend/ on sys.path

from sqlalchemy import select

# Every ORM model module must be imported before the first flush/commit, or
# SQLAlchemy's mapper can't resolve cross-domain FKs (e.g.
# ledger_entry.payment_account_id -> payment_account.id) even when this
# script never touches those tables directly. Same reason migrations/env.py
# imports all of these.
from src.auth.models import User  # noqa: F401
from src.cargo.models import (  # noqa: F401
    CargoAllocation,
    CargoCostBasis,
    CargoMode,
    CargoShipment,
)
from src.catalog.models import (  # noqa: F401
    Brand,
    Category,
    Item,
    ItemCompatibleModel,
    Model,
)
from src.database import SessionLocal
from src.expenses.models import (  # noqa: F401
    Expense,
    ExpenseCategory,
    RecurringExpenseTemplate,
)
from src.inventory import service as inventory_service
from src.inventory.models import StockLot, StockMovement  # noqa: F401
from src.inventory.schemas import StockLotReceiveCreate
from src.ledger import service as ledger_service
from src.ledger.models import LedgerEntry  # noqa: F401
from src.models import Setting  # noqa: F401
from src.parties import service as parties_service
from src.parties.models import Party
from src.parties.schemas import PartyCreate
from src.payments.models import (  # noqa: F401
    PaymentAccount,
    PaymentMethod,
    PaymentTransaction,
)
from src.purchasing import service as purchasing_service
from src.purchasing.models import (  # noqa: F401
    ExchangeRate,
    PurchaseOrder,
    PurchaseOrderLine,
)
from src.purchasing.schemas import (
    PurchaseOrderCreate,
    PurchaseOrderLineCreate,
)
from src.purchasing.utils import money
from src.sales.models import (  # noqa: F401
    SalesOrder,
    SalesOrderLine,
    SalesOrderLineLot,
)

CSV_PATH = os.environ.get("SHOP_DETAIL_CSV", "/tmp/shop_detail_preview.csv")
VENDOR_NAME = "Mohsin"
TODAY = date.today()


async def get_or_create_category(session, name: str) -> Category:
    existing = await session.scalar(select(Category).where(Category.name == name))
    if existing:
        return existing
    row = Category(name=name)
    session.add(row)
    await session.flush()
    print(f"Created Category '{name}'.")
    return row


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


def slug(text: str) -> str:
    return "".join(c for c in text.upper() if c.isalnum())


async def unique_sku(session, base: str) -> str:
    candidate = base
    n = 2
    while await session.scalar(select(Item.id).where(Item.sku == candidate)):
        candidate = f"{base}-{n}"
        n += 1
    return candidate


CATEGORY_SKU_PREFIX = {
    "OG Glass Protector": "PROT",  # matches seed_protectors.py's existing "PROT-BRAND-MODEL" convention
    "OG Finger Protector": "OGFNG",
    "TPU Case": "TPU",
    "Dust Plug": "DPLUG",
    "Polish Glass Protector": "POLGL",
    "Bolt Lens Protector": "BOLTL",
    "Simple Lens Protector": "SMPLL",
    "Membrane Sheet Protector": "MEMSH",
    "Camera Glass Protector": "CAMGL",
    "Clear Borderless Glass Protector": "CLRBL",
    "Full Cover Bordered Glass Protector": "FULCV",
    "Jun Best Lens Protector": "JUNBL",
    "UV Glass Protector": "UVGLS",
    "Matt Privacy Glass Protector": "MATTP",
    "Dust Proof Privacy Protector": "DPPRV",
    "Simple Privacy Protector": "SMPPV",
    "Its Me Privacy Protector": "ITSME",
}


async def get_or_create_item(session, category: Category, model: Model, variant: str | None, compatible_models: list[Model]) -> Item:
    existing = await session.scalar(
        select(Item).where(
            Item.category_id == category.id,
            Item.model_id == model.id,
            Item.variant.is_(None) if not variant else Item.variant == variant,
        )
    )
    if existing:
        return existing
    prefix = CATEGORY_SKU_PREFIX[category.name]
    base_sku = f"{prefix}-{slug(model.name)}"
    if variant:
        base_sku += f"-{slug(variant)}"
    sku = await unique_sku(session, base_sku)
    row = Item(category_id=category.id, model_id=model.id, sku=sku, variant=variant, compatible_models=compatible_models)
    session.add(row)
    await session.flush()
    print(f"Created Item '{sku}' ({model.name}{' ' + variant if variant else ''}).")
    return row


def load_line_specs(csv_path: str) -> dict[str, list[dict]]:
    """row_id -> ordered list of {brand, model, variant} token dicts (first = primary)."""
    groups: dict[str, list[dict]] = defaultdict(list)
    meta: dict[str, dict] = {}
    with open(csv_path) as f:
        for row in csv.DictReader(f):
            groups[row["row_id"]].append({"brand": row["brand"], "model": row["model"], "variant": row["variant"] or None})
            meta[row["row_id"]] = {
                "sheet": row["sheet"],
                "category": row["category"],
                "received_qty": Decimal(row["received_qty"]),
                "rate_pkr": Decimal(row["rate_pkr"]),
            }
    return groups, meta


async def main() -> None:
    groups, meta = load_line_specs(CSV_PATH)
    print(f"Loaded {len(groups)} row groups from {CSV_PATH}\n")

    async with SessionLocal() as session:
        # --- Party ---
        mohsin = await session.scalar(select(Party).where(Party.name == VENDOR_NAME))
        if not mohsin:
            mohsin = await parties_service.create_party(
                session, PartyCreate(name=VENDOR_NAME, roles=["local_vendor"])
            )
            print(f"Created Party '{VENDOR_NAME}' (id={mohsin.id}).")
        else:
            print(f"Using existing Party '{VENDOR_NAME}' (id={mohsin.id}).")

        # --- Catalog: Category / Brand / Model / Item, one pass, one commit ---
        categories: dict[str, Category] = {}
        brands: dict[str, Brand] = {}
        models: dict[tuple[str, str], Model] = {}
        items: dict[str, Item] = {}  # row_id -> Item

        async def brand_for(name: str) -> Brand:
            if name not in brands:
                brands[name] = await get_or_create_brand(session, name)
            return brands[name]

        async def model_for(brand_name: str, model_name: str) -> Model:
            key = (brand_name, model_name)
            if key not in models:
                brand = await brand_for(brand_name)
                models[key] = await get_or_create_model(session, brand, model_name)
            return models[key]

        for row_id, tokens in groups.items():
            category_name = meta[row_id]["category"]
            if category_name not in categories:
                categories[category_name] = await get_or_create_category(session, category_name)
            category = categories[category_name]

            primary = tokens[0]
            primary_model = await model_for(primary["brand"], primary["model"])
            compatible = []
            seen_compatible = set()
            for tok in tokens[1:]:
                key = (tok["brand"], tok["model"])
                if key == (primary["brand"], primary["model"]) or key in seen_compatible:
                    continue
                seen_compatible.add(key)
                compatible.append(await model_for(tok["brand"], tok["model"]))

            item = await get_or_create_item(session, category, primary_model, primary["variant"], compatible)
            items[row_id] = item

        await session.commit()
        print(f"\nCatalog phase done: {len(categories)} categories, {len(brands)} brands, "
              f"{len(models)} models, {len(items)} items (existing + new).\n")

        # --- Purchase orders: one per category, receive every line, offset the payable ---
        by_category: dict[str, list[str]] = defaultdict(list)
        for row_id in groups:
            by_category[meta[row_id]["category"]].append(row_id)

        total_qty = Decimal(0)
        total_value = Decimal(0)
        for category_name, row_ids in by_category.items():
            lines_payload = [
                PurchaseOrderLineCreate(
                    item_id=items[rid].id,
                    qty=meta[rid]["received_qty"],
                    rate_pkr=meta[rid]["rate_pkr"],
                )
                for rid in row_ids
            ]
            po = await purchasing_service.create_purchase_order(
                session,
                PurchaseOrderCreate(party_id=mohsin.id, order_date=TODAY, source="local", lines=lines_payload),
            )
            print(f"Created PurchaseOrder #{po.id} for '{category_name}' ({len(lines_payload)} lines).")

            po_total = Decimal(0)
            for line in po.lines:
                lot = await inventory_service.receive_purchase_order_line(
                    session, StockLotReceiveCreate(purchase_order_line_id=line.id, received_date=TODAY)
                )
                po_total += money(lot.qty_received * lot.landed_cost_pkr)
                total_qty += lot.qty_received

            po_total = money(po_total)
            await ledger_service.post_entry(
                session,
                entry_date=TODAY,
                account="Accounts Payable",
                debit=po_total,
                reference_type="purchase_order",
                reference_id=po.id,
                party_id=mohsin.id,
            )
            await session.commit()
            total_value += po_total
            print(f"  Received all lines, offset Accounts Payable by {po_total} PKR.\n")

        print(f"Done. Total qty received: {total_qty}. Total inventory value: {total_value} PKR.")
        print("Accounts Payable to Mohsin has been offset back to zero for every PO created above.")


if __name__ == "__main__":
    asyncio.run(main())
