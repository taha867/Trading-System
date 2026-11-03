"""Backfill purchase_log_exception for the payable-only entries that already exist.

Seventeen September 2026 Local Purchase rows have a category but no phone model, so they were booked as
nothing but an Accounts Payable ledger entry (reference_type "local_purchase_exception", reference_id = the
day-book sheet row): sheet row 21 (A.Power Traders, by the Stage 2 import) and 16 rows from the Stage 3
import. The ledger row alone says nothing about WHAT was bought. This script writes one
purchase_log_exception row per ledger entry, taking the category, quantity, rate and supplier invoice from
the sheet, and links it to the ledger row. It changes no ledger entry, balance or stock.

Every row is cross-checked before anything is written: the sheet row's supplier must match the ledger
entry's party, its date must match, and qty x rate must equal the ledger credit. Any mismatch aborts.

Default is a READ-ONLY plan. `--rehearse` runs the whole write and always rolls it back (the only trace is
skipped id numbers). `--apply` writes in ONE transaction, aborts unless the result is exactly the approved
17 rows / Rs 119,875, and refuses to run if any of these entries already has a log row.

    DATABASE_URL=postgresql+asyncpg://... backend/.venv/bin/python \
        scripts/backfill_purchase_log_exceptions.py [--rehearse | --apply]
"""

import argparse
import asyncio
import datetime
import os
import re
import sys
from dataclasses import dataclass
from decimal import Decimal

import openpyxl

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend/ on sys.path

from sqlalchemy import select, text

# Every ORM model module must be imported before the first flush/commit.
from src.auth.models import User  # noqa: F401
from src.cargo.models import CargoAllocation, CargoCostBasis, CargoMode, CargoShipment  # noqa: F401
from src.catalog.models import Brand, Category, Item, ItemCompatibleModel, Model  # noqa: F401
from src.database import SessionLocal
from src.expenses.models import Expense, ExpenseCategory, RecurringExpenseTemplate  # noqa: F401
from src.inventory.models import StockLot, StockMovement  # noqa: F401
from src.ledger.models import LedgerEntry
from src.models import Setting  # noqa: F401
from src.parties.models import Party
from src.payments.models import PaymentAccount, PaymentMethod, PaymentTransaction  # noqa: F401
from src.purchasing.models import ExchangeRate, PurchaseLogException, PurchaseOrder, PurchaseOrderLine  # noqa: F401
from src.sales.models import SalesLogException, SalesOrder, SalesOrderLine, SalesOrderLineLot  # noqa: F401

SRC = "/home/m-taha/Desktop/upwork/shakeel accesories/Daily Cash Book/Daily Cash Book (Sept 2026).xlsx"
EXPECTED_ROWS = 17
EXPECTED_AMOUNT = Decimal("119875")  # 118,375 (Stage 3 payable-only rows) + 1,500 (A.Power Traders, row 21)

SUPPLIER_NAMES = {
    "galaxy mobile kamran": "Galaxy Mobile, Kamran", "s&a": "S&A", "alnafeh traders": "AlNafeh Traders",
    "javed traders": "Javed Traders", "ns traders": "NS Traders", "amt": "AMT", "a.power traders": "A.Power Traders",
}


class BackfillError(Exception):
    pass


def to_date(v):
    if isinstance(v, datetime.datetime):
        return v.date()
    s = str(v or "").strip()
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def clean(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).strip().lower())


@dataclass
class SheetRow:
    row: int
    date: datetime.date
    supplier: str
    invoice: str | None
    category: str | None
    qty: Decimal
    rate: Decimal

    @property
    def amount(self) -> Decimal:
        return self.qty * self.rate


def read_sheet_rows(wb, wanted: set[int]) -> dict[int, SheetRow]:
    """The wanted Local Purchase rows, with supplier and invoice resolved by block: a new Ledger Date or a
    new Supplier cell starts a block, and a block only has an invoice number if its own cell gives one."""
    ws = wb["Local Purchase"]
    headers = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]
    out, ld, sup, inv = {}, None, None, None
    for r in range(2, ws.max_row + 1):
        raw = {h: ws.cell(row=r, column=i + 1).value for i, h in enumerate(headers) if h}
        new_ld = to_date(raw.get("Ledger Date"))
        if new_ld:
            ld, sup, inv = new_ld, None, None
        if raw.get("Supplier") not in (None, ""):
            sup, inv = str(raw["Supplier"]), None
        if raw.get("Invoice #") not in (None, ""):
            inv = str(raw["Invoice #"])
        if r not in wanted:
            continue
        category = raw.get("Category") or raw.get("Model")  # row 21 puts "Membrane" in the Model column
        out[r] = SheetRow(r, ld, sup or "", inv, str(category) if category else None, Decimal(str(raw["Qty"])), Decimal(str(raw["Rate"])))
    return out


async def main(apply: bool, rehearse: bool) -> None:
    wb = openpyxl.load_workbook(SRC, data_only=True)
    async with SessionLocal() as db:
        entries = (await db.scalars(
            select(LedgerEntry).where(LedgerEntry.reference_type == "local_purchase_exception").order_by(LedgerEntry.reference_id)
        )).all()
        sheet = read_sheet_rows(wb, {e.reference_id for e in entries})
        parties = {p.id: p.name for p in (await db.scalars(select(Party))).all()}

        plan = []
        for e in entries:
            row = sheet.get(e.reference_id)
            if row is None:
                raise BackfillError(f"Ledger entry #{e.id}: sheet row {e.reference_id} not found")
            expected_party = SUPPLIER_NAMES.get(clean(row.supplier), row.supplier.strip())
            if parties.get(e.party_id) != expected_party:
                raise BackfillError(f"Sheet row {row.row}: supplier {expected_party!r} != ledger party {parties.get(e.party_id)!r}")
            if row.date != e.entry_date or row.amount != e.credit or e.debit != 0:
                raise BackfillError(f"Sheet row {row.row}: date/amount differ from ledger #{e.id} ({row.date} {row.amount} vs {e.entry_date} {e.credit})")
            plan.append((e, row))

        total = sum((e.credit for e, _ in plan), Decimal(0))
        print(f"payable-only ledger entries found: {len(plan)} | total Rs {total:,.0f}")
        for e, r in plan:
            print(f"  ledger #{e.id:<5} {e.entry_date} {parties[e.party_id][:22]:22} sheet row {r.row:<3} invoice {str(r.invoice):>5} {str(r.category)[:16]:16} {r.qty:>5} x {r.rate:<6} = {r.amount:>8,.0f}")
        if len(plan) != EXPECTED_ROWS or total != EXPECTED_AMOUNT:
            raise BackfillError(f"Expected {EXPECTED_ROWS} rows / Rs {EXPECTED_AMOUNT:,.0f}, found {len(plan)} / Rs {total:,.0f}")
        print("Plan matches the approved numbers exactly.")

        table_exists = await db.scalar(text("select to_regclass('purchase_log_exception') is not null"))
        if not table_exists:
            await db.rollback()
            print("[PLAN ONLY] The purchase_log_exception table does not exist yet — apply the migration first.")
            return
        already = await db.scalar(
            select(PurchaseLogException.id).where(PurchaseLogException.ledger_entry_id.in_([e.id for e, _ in plan])).limit(1)
        )
        if already is not None:
            raise BackfillError("Some of these entries already have a purchase_log_exception row — aborting, nothing written")
        if not apply and not rehearse:
            await db.rollback()
            print("[PLAN ONLY] Nothing was written. Re-run with --rehearse to test the write, or --apply to write it.")
            return

        try:
            for e, r in plan:
                db.add(PurchaseLogException(
                    entry_date=e.entry_date, kind="no_model", party_id=e.party_id, category_name=r.category,
                    qty=r.qty, rate_pkr=r.rate, amount_pkr=e.credit, invoice_number=r.invoice,
                    note=f"Day-book row {r.row}: category given, no model", ledger_entry_id=e.id,
                ))
            await db.flush()
            count, amount = (await db.execute(text("select count(*), coalesce(sum(amount_pkr), 0) from purchase_log_exception"))).one()
            if count != EXPECTED_ROWS or Decimal(amount) != EXPECTED_AMOUNT:
                raise BackfillError(f"Final check failed: {count} rows / Rs {amount} in the table")
            print(f"Final check passed: {count} rows, Rs {Decimal(amount):,.0f}")
        except Exception:
            await db.rollback()
            raise
        if rehearse:
            await db.rollback()
            print("[REHEARSAL OK] The whole write ran and passed every check, then was rolled back. Nothing persisted.")
            return
        await db.commit()
        print("COMMITTED.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--rehearse", action="store_true", help="run the full write, then always roll it back")
    group.add_argument("--apply", action="store_true", help="write to the database (default: read-only plan)")
    args = parser.parse_args()
    asyncio.run(main(args.apply, args.rehearse))
