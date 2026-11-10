"""STATUS: ALREADY APPLIED TO PRODUCTION (October 2026). DO NOT RE-RUN WITH --apply.
The resume checks below compare invoice numbers that were later corrected in production (the carried-down
invoice numbers were cleared), so a re-run would no longer recognise what it already wrote and would create
DUPLICATE purchases, stock lots, sales and ledger entries. `--apply` therefore refuses to run unless
`--i-understand-this-already-ran-in-production` is also passed. A dry run (no --apply) is still safe.
See PRODUCTION_CHANGES_LOG.md for what was applied and changed afterwards.

Day-book catch-up, Stage 2a: September 2026 Credit Sale rows that cannot become
a normal SalesOrder -- cancelled invoices, bulk/mixed-model batches, blank-model
lines, and price corrections/discounts.

None of these have a specific catalog Item, so none of them touch StockLot/FIFO.
Per the user's explicit decision: post the real money to the party's ledger as
usual (so receivables stay correct and the row isn't silently lost), but record
qty/category/rate in a separate `sales_log_exception` row rather than a real
SalesOrderLine -- "we can skip the stock deduction thing but we will keep track
of how many pieces and price category models are not deducted from stock."

A cancelled invoice (amount 0) gets a log row only, no ledger entry at all --
there is no money to post, it exists purely so the invoice-number sequence
doesn't look like an unexplained gap later.

This is Stage 2a specifically (not the full Credit Sale sheet) -- the ~455
rows with a specific item still need catalog cross-matching and are handled
by a separate stage 2b script.

Run with the backend's own venv:
    DATABASE_URL=... backend/.venv/bin/python scripts/import_daybook_sept2026_stage2a_exceptions.py [--apply]
"""

import argparse
import asyncio
import datetime
import os
import sys
from decimal import Decimal

import openpyxl

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend/ on sys.path

from sqlalchemy import select

# Every ORM model module must be imported before the first flush/commit.
from src.auth.models import User  # noqa: F401
from src.cargo.models import CargoAllocation, CargoCostBasis, CargoMode, CargoShipment  # noqa: F401
from src.catalog.models import Brand, Category, Item, ItemCompatibleModel, Model  # noqa: F401
from src.database import SessionLocal
from src.expenses.models import Expense, ExpenseCategory, RecurringExpenseTemplate  # noqa: F401
from src.inventory.models import StockLot, StockMovement  # noqa: F401
from src.ledger import service as ledger_service
from src.ledger.models import LedgerEntry  # noqa: F401
from src.models import Setting  # noqa: F401
from src.parties.constants import PartyRole
from src.parties.models import Party
from src.payments.models import PaymentAccount, PaymentMethod, PaymentTransaction  # noqa: F401
from src.purchasing.models import ExchangeRate, PurchaseOrder, PurchaseOrderLine  # noqa: F401
from src.sales.models import SalesLogException, SalesOrder, SalesOrderLine, SalesOrderLineLot  # noqa: F401

SRC = "/home/m-taha/Desktop/upwork/shakeel accesories/Daily Cash Book/Daily Cash Book (Sept 2026).xlsx"

NEW_PARTIES = [
    ("S&A", [PartyRole.CUSTOMER, PartyRole.LOCAL_VENDOR]),
]

PARTY_NAME_MAP = {
    "dream mobile sargodha": "DREAM MOB SARGODAH",
    "waseem mobile mazafargarh": "WASEEM MB MUZAFFARGARH",
    "osama mobile arifwala": "OSAMA MOBILE ARIFWALA",
    "s&a": "S&A",
    "sonu traders khawali lakhan": "SONU MOBILE HAVALI LAKKA",
    "shoaib mobile jhang": "Shoaib Mobile, Jhang",
    "mobile store khanewal": "Mobile Store, Khanewal",
    "m.h mobile abdul hakeem": "MH MOB ABDULHAKEEM",
    "jilani mobile d.i khan": "GILLANI MOB DI KHAN",
    "gadget valley": "GADGET VALLEY FSD",
    "hasan man mobile shekhupura": "Hasan Man, Sheikhupura",
}


def to_date(v) -> datetime.date | None:
    if v is None:
        return None
    if isinstance(v, datetime.datetime):
        return v.date()
    if isinstance(v, datetime.date):
        return v
    s = str(v).strip()
    if not s:
        return None
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    raise ValueError(f"Unparseable date: {v!r}")


def read_credit_sale_sept(wb):
    ws = wb["Credit Sale"]
    headers = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]
    rows = []
    last_ledger_date = None
    last_customer = None
    last_invoice = None
    for r in range(2, ws.max_row + 1):
        raw = {h: ws.cell(row=r, column=i + 1).value for i, h in enumerate(headers) if h}
        ld = to_date(raw.get("Ledger Date"))
        if ld is not None:
            last_ledger_date = ld
            last_customer = None
            last_invoice = None

        cust = raw.get("Customer")
        if cust is not None and str(cust).strip() != "":
            last_customer = cust
        else:
            cust = last_customer

        inv = raw.get("INVOICE#")
        if inv is not None and str(inv).strip() != "":
            last_invoice = inv
        else:
            inv = last_invoice

        rows.append(
            {
                "_row": r,
                "Ledger Date": last_ledger_date,
                "Amount": raw.get("Amount"),
                "Qty": raw.get("Qty"),
                "Rate": raw.get("Rate"),
                "Category": raw.get("Category"),
                "Model": raw.get("Model"),
                "Customer": cust,
                "INVOICE#": inv,
                "Comment": raw.get("Comment"),
            }
        )
    return [r for r in rows if r["Ledger Date"] and r["Ledger Date"].year == 2026 and r["Ledger Date"].month == 9]


def classify(row) -> str | None:
    if row["Comment"] == "invoice was cancelled":
        return "cancelled_invoice"
    if row["Category"] in ("Correction", "Discount"):
        return row["Category"].lower()
    if row["Qty"] and row["Rate"] is not None and row["Category"]:
        if row["Model"] == "(Bulk, mixed models)":
            return "bulk_mixed_models"
        if not row["Model"]:
            return "blank_model"
    return None  # not an exception row -- handled by stage 2b instead


def _resolve_amount(row) -> Decimal:
    # The sheet's own convention for "cash invoice, money already recorded in
    # Received Amount" rows (e.g. #37, Hasan Man Sheikhupura) is to leave Amount
    # blank entirely rather than 0, even though qty/rate ARE real -- same as
    # every real SalesOrderLine, amount is qty*rate, never a separately stored
    # value, so fall back to computing it rather than treating blank as zero.
    if row["Amount"]:
        return Decimal(str(row["Amount"]))
    if row["Qty"] and row["Rate"] is not None:
        return Decimal(str(row["Qty"])) * Decimal(str(row["Rate"]))
    return Decimal(0)


async def resolve_party(db, cache: dict, raw_name: str | None) -> Party | None:
    if not raw_name:
        return None
    canonical = PARTY_NAME_MAP.get(raw_name.strip().lower(), raw_name.strip())
    if canonical in cache:
        return cache[canonical]
    party = await db.scalar(select(Party).where(Party.name == canonical))
    if party is None:
        raise RuntimeError(f"Party {canonical!r} (from {raw_name!r}) not found -- expected to be pre-created")
    cache[canonical] = party
    return party


async def main(apply: bool) -> None:
    wb = openpyxl.load_workbook(SRC, data_only=True)
    rows = read_credit_sale_sept(wb)

    exceptions = []
    for row in rows:
        kind = classify(row)
        if kind:
            exceptions.append((kind, row))

    print(f"Exception rows found: {len(exceptions)}")
    for kind, row in exceptions:
        print(f"  row {row['_row']:4d} [{kind:18s}] {row['Ledger Date']} amount={row['Amount']} "
              f"qty={row['Qty']} rate={row['Rate']} cat={row['Category']!r} customer={row['Customer']!r} "
              f"invoice#={row['INVOICE#']}")

    async with SessionLocal() as db:
        # Lookup resolution runs unconditionally (even dry-run), matching this
        # codebase's established script convention -- only the actual log/ledger
        # writes below are gated behind --apply.
        created_parties = []
        for name, roles in NEW_PARTIES:
            existing = await db.scalar(select(Party).where(Party.name == name))
            if existing is None:
                db.add(Party(name=name, roles=[r.value for r in roles], opening_balance=Decimal(0)))
                created_parties.append(name)
        await db.commit()
        print(f"\nNew parties created: {created_parties or '(none -- already existed)'}")

        party_cache: dict = {}

        total_posted = Decimal(0)
        total_logged_zero = 0
        for kind, row in exceptions:
            party = await resolve_party(db, party_cache, row["Customer"])
            amount = _resolve_amount(row)
            if amount != 0:
                total_posted += amount
            else:
                total_logged_zero += 1

        print(f"\nTotal non-zero exception amount to post to ledger: {total_posted}")
        print(f"Zero-amount (cancelled invoice) rows, log only: {total_logged_zero}")

        if not apply:
            print("\n[DRY RUN] Nothing written. Re-run with --apply to commit.")
            return

        for kind, row in exceptions:
            party = await resolve_party(db, party_cache, row["Customer"])
            amount = _resolve_amount(row)
            qty = Decimal(str(row["Qty"])) if row["Qty"] else None
            rate = Decimal(str(row["Rate"])) if row["Rate"] is not None else None

            log = SalesLogException(
                entry_date=row["Ledger Date"],
                kind=kind,
                category_name=row["Category"],
                qty=qty,
                rate_pkr=rate,
                amount_pkr=amount,
                party_id=party.id if party else None,
                invoice_number=str(row["INVOICE#"]) if row["INVOICE#"] is not None else None,
                note=row["Model"] if row["Model"] and row["Model"] != "(Bulk, mixed models)" else None,
            )
            db.add(log)
            await db.flush()  # log.id needed by the ledger reference below

            if amount != 0 and party is not None:
                entry = await ledger_service.post_entry(
                    db,
                    entry_date=row["Ledger Date"],
                    account="Accounts Receivable",
                    debit=amount if amount > 0 else Decimal(0),
                    credit=-amount if amount < 0 else Decimal(0),
                    reference_type="sales_log_exception",
                    reference_id=log.id,
                    party_id=party.id,
                )
                await db.flush()
                log.ledger_entry_id = entry.id

        await db.commit()
        print(f"\nDone. {len(exceptions)} exception rows logged, ledger posted for {len(exceptions) - total_logged_zero} of them.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument(
        "--i-understand-this-already-ran-in-production",
        action="store_true",
        dest="override_already_ran",
        help="required with --apply: this import was already applied; re-running it can double-write data",
    )
    args = parser.parse_args()
    if args.apply and not args.override_already_ran:
        raise SystemExit(
            "Refusing to --apply: this import was already applied to production and a re-run can double-write "
            "purchases, stock, sales and ledger entries. Read the STATUS note at the top of this file."
        )
    asyncio.run(main(args.apply))
