"""One-off follow-up to import_shop_detail_batch_20260921.py: the Polish
Glass Protector sheet row "A3 (2016)/17" (299 pcs) that was deliberately
excluded from that batch as unresolved.

Confirmed with the user afterward: this is Samsung Galaxy A3, and the "/17"
is a "/"-separated compatible-model group covering both the Galaxy A3
(2016) and Galaxy A3 (2017) variants sharing one combined quantity -- same
pattern as "A7 2017" already resolving to "Galaxy A7 (2017)" via
TOKEN_OVERRIDES, and the same "/"-compatible-model handling used throughout
the 2026-09-21 batch (e.g. Reno 2/F19).

Run with the backend's own venv (needs the app's DB session/services):
    DATABASE_URL=... backend/.venv/bin/python scripts/import_shop_detail_batch_20260921_a3.py [--apply]
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
from src.catalog.models import Brand, Category, Item, Model
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
QTY = Decimal(299)


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
    sku = await unique_sku(session, f"POLGL-{slug(model.name)}")
    row = Item(category_id=category.id, model_id=model.id, sku=sku, variant=None, compatible_models=compatible_models)
    session.add(row)
    await session.flush()
    print(f"Created Item '{sku}' ({model.name}).")
    return row


async def main(apply: bool) -> None:
    async with SessionLocal() as session:
        mohsin = await session.scalar(select(Party).where(Party.name == VENDOR_NAME))
        if not mohsin:
            raise RuntimeError(f"Party '{VENDOR_NAME}' not found -- expected to already exist")
        polish_glass = await session.scalar(select(Category).where(Category.name == "Polish Glass Protector"))
        if not polish_glass:
            raise RuntimeError("Category 'Polish Glass Protector' not found -- expected to already exist")

        samsung = await get_or_create_brand(session, "Samsung")
        a3_2016 = await get_or_create_model(session, samsung, "Galaxy A3 (2016)")
        a3_2017 = await get_or_create_model(session, samsung, "Galaxy A3 (2017)")
        item = await get_or_create_item(session, polish_glass, a3_2016, [a3_2017])
        await session.commit()

        if not apply:
            print(f"\n[DRY RUN] Polish Glass Protector PO: item {item.id} ({item.sku}), qty {QTY}")
            print("\nDRY RUN -- catalog rows above were created for real (get-or-create is idempotent-safe on "
                  "re-run), but no purchase order, receipt, or ledger entry was created. Re-run with --apply to commit.")
            return

        lines_payload = [PurchaseOrderLineCreate(item_id=item.id, qty=QTY, rate_pkr=POLISH_GLASS_RATE)]
        po = await purchasing_service.create_purchase_order(
            session, PurchaseOrderCreate(party_id=mohsin.id, order_date=TODAY, source="local", lines=lines_payload)
        )
        print(f"Created PurchaseOrder #{po.id} for 'Polish Glass Protector' (1 line).")

        lot = await inventory_service.receive_purchase_order_line(
            session, StockLotReceiveCreate(purchase_order_line_id=po.lines[0].id, received_date=TODAY)
        )
        po_total = money(lot.qty_received * lot.landed_cost_pkr)

        await ledger_service.post_entry(
            session, entry_date=TODAY, account="Accounts Payable", debit=po_total,
            reference_type="purchase_order", reference_id=po.id, party_id=mohsin.id,
        )
        await session.commit()
        print(f"Received {lot.qty_received} pcs, offset Accounts Payable by {po_total} PKR.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.apply))
