"""One-off: receive a new Dust Plug stock batch from Mohsin (2026-09-09 message).

Nine lines, several against models that don't exist in the catalog yet (Vivo
Y20/Y33S/V23E/V23, Samsung A55, Infinix "Hot 30" plain, and a brand-new
"Pixel" brand + "Pixel 6" model). Mirrors import_shop_detail.py's pattern:
get-or-create the missing catalog rows, one PurchaseOrder (source="local",
vendor=Mohsin) for the whole batch, receive every line into a StockLot, then
post an offsetting Accounts Payable debit -- confirmed with the user this is
not a real debt to record, same treatment as the earlier partnership import.

Run with the backend's own venv (needs the app's DB session/services):
    DATABASE_URL=... backend/.venv/bin/python scripts/add_dust_plug_stock_batch.py
"""

import asyncio
import os
import sys
from datetime import date
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend/ on sys.path

from sqlalchemy import select

# Every ORM model module must be imported before the first flush/commit, or
# SQLAlchemy's mapper can't resolve cross-domain FKs -- same reason
# migrations/env.py and import_shop_detail.py both do this.
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
CATEGORY_NAME = "Dust Plug"
SKU_PREFIX = "DPLUG"
RATE_PKR = Decimal("82.51")
TODAY = date.today()

# (brand, model, qty) -- category is Dust Plug for every row (confirmed by the user).
BATCH = [
    ("Vivo", "Y20", Decimal(250)),
    ("Vivo", "Y31", Decimal(70)),
    ("Vivo", "Y33S", Decimal(50)),
    ("Vivo", "V23E", Decimal(40)),
    ("Vivo", "V23", Decimal(14)),
    ("Samsung", "A55", Decimal(50)),  # corrected from 150 per the user
    ("iPhone", "iPhone 11", Decimal(9)),  # "IP11" in the message -> existing "iPhone 11" model
    ("Infinix", "Hot 30", Decimal(30)),
    ("Pixel", "Pixel 6", Decimal(72)),
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


async def get_or_create_item(session, category: Category, model: Model) -> Item:
    existing = await session.scalar(
        select(Item).where(Item.category_id == category.id, Item.model_id == model.id, Item.variant.is_(None))
    )
    if existing:
        return existing
    sku = await unique_sku(session, f"{SKU_PREFIX}-{slug(model.name)}")
    row = Item(category_id=category.id, model_id=model.id, sku=sku, variant=None, is_active=True)
    session.add(row)
    await session.flush()
    print(f"Created Item '{sku}' ({model.name}).")
    return row


async def main() -> None:
    async with SessionLocal() as session:
        mohsin = await session.scalar(select(Party).where(Party.name == VENDOR_NAME))
        if not mohsin:
            raise RuntimeError(f"Party '{VENDOR_NAME}' not found -- expected to already exist")

        category = await session.scalar(select(Category).where(Category.name == CATEGORY_NAME))
        if not category:
            raise RuntimeError(f"Category '{CATEGORY_NAME}' not found -- expected to already exist")

        items: list[tuple[Item, Decimal]] = []
        for brand_name, model_name, qty in BATCH:
            brand = await get_or_create_brand(session, brand_name)
            model = await get_or_create_model(session, brand, model_name)
            item = await get_or_create_item(session, category, model)
            items.append((item, qty))

        await session.commit()
        print(f"\nCatalog phase done: {len(items)} items resolved (existing + new).\n")

        lines_payload = [
            PurchaseOrderLineCreate(item_id=item.id, qty=qty, rate_pkr=RATE_PKR) for item, qty in items
        ]
        po = await purchasing_service.create_purchase_order(
            session,
            PurchaseOrderCreate(party_id=mohsin.id, order_date=TODAY, source="local", lines=lines_payload),
        )
        print(f"Created PurchaseOrder #{po.id} ({len(lines_payload)} lines).")

        po_total = Decimal(0)
        total_qty = Decimal(0)
        for line in po.lines:
            lot = await inventory_service.receive_purchase_order_line(
                session, StockLotReceiveCreate(purchase_order_line_id=line.id, received_date=TODAY)
            )
            po_total += money(lot.qty_received * lot.landed_cost_pkr)
            total_qty += lot.qty_received
        po_total = money(po_total)

        # Not a real debt (confirmed with the user) -- offset the payable back to
        # zero, same treatment as the original partnership-split import.
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

        print(f"\nReceived all lines. Total qty: {total_qty}. Total inventory value: {po_total} PKR.")
        print("Accounts Payable to Mohsin offset back to zero for this PO.")


if __name__ == "__main__":
    asyncio.run(main())
