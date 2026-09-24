"""One-off: add the 21 "Shakeel SB" parties from the business-split balance
sheet (Mohsin_Warraich_Balance_Sheet.xlsx, "Shop Parties Ledger" sheet) as
new Parties with an opening balance, confirmed with the user 2026-09-24.

Sign convention (matches Party.opening_balance / create_party's ledger
posting): positive = the party owes the shop (receivable), negative = the
shop owes the party (payable).

Roles, confirmed with the user: receivable parties -> customer, payable
parties -> local_vendor.

Two rows from the sheet's "Shakeel SB" column were marked "NOT INCUDED" and
are deliberately excluded per the user's instruction (JAVAID MB H/C, Al
GHANI MOBILE MULTAN). One data-quality note surfaced to the user but not
auto-corrected: SALEMAN FARUKH's overall RECEIVABLE column reads 53,329
while its own Shakeel SB column reads 57,329 -- this script uses the
Shakeel SB figure (57,329) as instructed.

Run with the backend's own venv:
    DATABASE_URL=... backend/.venv/bin/python scripts/add_shakeel_sb_opening_balances.py [--apply]
"""

import argparse
import asyncio
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend/ on sys.path

from sqlalchemy import select

# Every ORM model module must be imported before the first flush/commit.
from src.auth.models import User  # noqa: F401
from src.cargo.models import CargoAllocation, CargoCostBasis, CargoMode, CargoShipment  # noqa: F401
from src.catalog.models import Brand, Category, Item, ItemCompatibleModel, Model  # noqa: F401
from src.database import SessionLocal
from src.expenses.models import Expense, ExpenseCategory, RecurringExpenseTemplate  # noqa: F401
from src.inventory.models import StockLot, StockMovement  # noqa: F401
from src.ledger.models import LedgerEntry  # noqa: F401
from src.models import Setting  # noqa: F401
from src.parties import service as parties_service
from src.parties.models import Party
from src.parties.schemas import PartyCreate
from src.payments.models import PaymentAccount, PaymentMethod, PaymentTransaction  # noqa: F401
from src.purchasing.models import ExchangeRate, PurchaseOrder, PurchaseOrderLine  # noqa: F401
from src.sales.models import SalesOrder, SalesOrderLine, SalesOrderLineLot  # noqa: F401

# (name, opening_balance) -- positive = receivable (customer), negative = payable (local_vendor)
PARTIES: list[tuple[str, Decimal]] = [
    ("GADGET VALLEY FSD", Decimal(134171)),
    ("SHAHZAD MB ARIFWALA", Decimal(24180)),
    ("APNA TECH GUJ", Decimal(13370)),
    ("WASEEM MB MUZAFFARGARH", Decimal(152644)),
    ("TASHFEEN TRADERS MULTAN", Decimal(89155)),
    ("DREAM MOB SARGODAH", Decimal(33669)),
    ("GEO MOB CHISTIAN", Decimal(28805)),
    ("SALEMAN FARUKH", Decimal(57329)),
    ("SHEIKH FURQAN OKARA", Decimal(214415)),
    ("GILLANI MOB DI KHAN", Decimal(48600)),
    ("ZOHAIB MOB DI KHAN", Decimal(9200)),
    ("MH MOB ABDULHAKEEM", Decimal(67170)),
    ("USMAN MB SUMMUNDRI", Decimal(22130)),
    ("SONU MOBILE HAVALI LAKKA", Decimal(7276)),
    ("SHAKEEL WAHALA", Decimal(15000)),
    ("AHMAD MOB MAILSEE", Decimal(-2150)),
    ("S-I TRADERS", Decimal(-6000)),
    ("Amaya MMZ", Decimal(-6000)),
    ("sunny mobile shikarpoor", Decimal(-2600)),
    ("OSAMA MOBILE ARIFWALA", Decimal(-3322)),
    ("ZAHEER WAHALA", Decimal(-24900)),
]


async def main(apply: bool) -> None:
    async with SessionLocal() as session:
        if not apply:
            print(f"[DRY RUN] Would create {len(PARTIES)} Party row(s):")
            for name, balance in PARTIES:
                role = "customer" if balance > 0 else "local_vendor"
                existing = await session.scalar(select(Party).where(Party.name == name))
                flag = "  <-- WARNING: a Party with this exact name already exists!" if existing else ""
                print(f"  {name!r}: role={role}, opening_balance={balance}{flag}")
            print("\nDRY RUN -- nothing written. Re-run with --apply to commit.")
            return

        created = []
        for name, balance in PARTIES:
            role = "customer" if balance > 0 else "local_vendor"
            party = await parties_service.create_party(
                session, PartyCreate(name=name, roles=[role], opening_balance=balance)
            )
            created.append((party.id, party.name, role, balance))

        print(f"Created {len(created)} Party row(s):")
        for pid, name, role, balance in created:
            print(f"  id={pid} name={name!r} role={role} opening_balance={balance}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    asyncio.run(main(args.apply))
