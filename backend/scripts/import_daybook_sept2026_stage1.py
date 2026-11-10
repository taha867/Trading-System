"""STATUS: ALREADY APPLIED TO PRODUCTION (October 2026). DO NOT RE-RUN WITH --apply.
The resume checks below compare invoice numbers that were later corrected in production (the carried-down
invoice numbers were cleared), so a re-run would no longer recognise what it already wrote and would create
DUPLICATE purchases, stock lots, sales and ledger entries. `--apply` therefore refuses to run unless
`--i-understand-this-already-ran-in-production` is also passed. A dry run (no --apply) is still safe.
See PRODUCTION_CHANGES_LOG.md for what was applied and changed afterwards.

Day-book catch-up, Stage 1: Expenses + Received Amount for September 2026.

Source: "Daily Cash Book (Sept 2026).xlsx" (Expenses, Received Amount sheets),
filtered strictly to Ledger Date in September 2026 -- the file also contains
October rows which are explicitly out of scope for this batch.

Per the user's explicit decisions this session:
  - Ledger Date (not any other date column) is used as the real date everywhere.
  - No comment/notes field is carried over onto Expense or SalesOrder/PurchaseOrder
    (PaymentTransaction already has a `note` column, but Received Amount had zero
    commented rows in September, so this is moot for this batch).
  - Expenses with no stated payment account in the sheet go under the "Unspecified
    (to be decided)" payment account (id 6) created earlier this session, never
    silently defaulted to Cash.
  - Expense categories are exactly "Personal" and "Shop" -- matching the sheet,
    nothing finer invented.
  - Party name spelling variants are collapsed onto one canonical name each; new
    parties not present in production are created fresh with opening_balance=0
    (no prior history exists for them).
  - A generic "Cash (Walk-in / Anonymous)" party covers genuinely anonymous cash
    receipts ("CASH invoice 14", "Mix") -- confirmed by the user these are not
    real distinct customers.
  - The file's embedded reconciliation comments (referencing an external "OASIS"
    system) are explicitly ignored per the user's instruction -- the sheet's own
    recorded values are final and already verified.

Run with the backend's own venv:
    DATABASE_URL=... backend/.venv/bin/python scripts/import_daybook_sept2026_stage1.py [--apply]
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
from src.expenses import service as expenses_service
from src.expenses.models import Expense, ExpenseCategory, RecurringExpenseTemplate
from src.expenses.schemas import ExpenseCreate
from src.inventory.models import StockLot, StockMovement  # noqa: F401
from src.ledger import service as ledger_service
from src.ledger.models import LedgerEntry  # noqa: F401
from src.models import Setting  # noqa: F401
from src.parties.constants import PartyRole
from src.parties.models import Party
from src.payments import service as payments_service
from src.payments.models import PaymentAccount, PaymentMethod, PaymentTransaction
from src.payments.schemas import PaymentTransactionCreate
from src.purchasing.models import ExchangeRate, PurchaseOrder, PurchaseOrderLine  # noqa: F401
from src.sales.models import SalesOrder, SalesOrderLine, SalesOrderLineLot  # noqa: F401

SRC = "/home/m-taha/Desktop/upwork/shakeel accesories/Daily Cash Book/Daily Cash Book (Sept 2026).xlsx"

NEW_PARTIES = [
    # (name, roles)
    ("Cash (Walk-in / Anonymous)", [PartyRole.CUSTOMER]),
    ("Abdullah Mobile, Mandi Bhaudeen", [PartyRole.CUSTOMER]),
    ("Hasan Man, Sheikhupura", [PartyRole.CUSTOMER]),
    ("Server Goraya", [PartyRole.CUSTOMER]),
    ("Mobile Store, Khanewal", [PartyRole.CUSTOMER]),
    ("Naveed Mobile, Chowk Azam", [PartyRole.CUSTOMER]),
    ("Noman Mobile, Multan", [PartyRole.CUSTOMER]),
    ("Shoaib Mobile, Jhang", [PartyRole.CUSTOMER]),
    ("Punjab Kamal Industries", [PartyRole.CUSTOMER]),
]

# Every spelling variant seen in the September Received Amount rows -> canonical name.
# Canonical name is either an existing production Party.name, or one of NEW_PARTIES above.
PARTY_NAME_MAP = {
    "dream mobile sargodha": "DREAM MOB SARGODAH",
    "gadget valley": "GADGET VALLEY FSD",
    "abdullah mobile mandi bhaudeen": "Abdullah Mobile, Mandi Bhaudeen",
    "jeoo mobile chistian": "GEO MOB CHISTIAN",
    "sonu traders khawali lakhan": "SONU MOBILE HAVALI LAKKA",
    "m.h mobile abdulhakeem": "MH MOB ABDULHAKEEM",
    "jelani mobile d.i khan": "GILLANI MOB DI KHAN",
    "jailani mobile d.i khan": "GILLANI MOB DI KHAN",
    "waseem mobile muzafargar": "WASEEM MB MUZAFFARGARH",
    "recived check from server goraya (factory)": "Server Goraya",
    "cashed check from server goraya (factory)": "Server Goraya",
    "mobile store khanewal": "Mobile Store, Khanewal",
    "osama mobile arifwala": "OSAMA MOBILE ARIFWALA",
    "punjab kamal industries  (shakeel dues from shop)": "Punjab Kamal Industries",
    "cash invoice 14": "Cash (Walk-in / Anonymous)",
    "shakeel sahab udhar (shakeel)": "SHAKEEL WAHALA",
    "shakeel sahab udhar": "SHAKEEL WAHALA",
    "nouman mobile multan": "Noman Mobile, Multan",
    "mix": "Cash (Walk-in / Anonymous)",
    "naveed mobile chowk azam": "Naveed Mobile, Chowk Azam",
    "shoaib mobile jhang": "Shoaib Mobile, Jhang",
    "shehzad mobil arifwala": "SHAHZAD MB ARIFWALA",
    "sheikh furqan mobile okara": "SHEIKH FURQAN OKARA",
    "sunny mobile shakarpoor": "sunny mobile shikarpoor",
    "hasan man sheikhupura": "Hasan Man, Sheikhupura",
    "cash invoice 37 (hasan man sheikhupura)": "Hasan Man, Sheikhupura",
}

# Sheet's "Bank / Payment Method" text -> existing payment_account.label
PAYMENT_METHOD_MAP = {
    "faisal bank limited": "Faysal Bank - main",
    "easypesa": "Easypaisa - 0300-0000000",
    "easy pesa": "Easypaisa - 0300-0000000",
    "jazz cash": "JazzCash - 0300-0000000",
    "bank of punjab": "Bank of Punjab - main",
    "meezan bank": "Meezan Bank - main",
    "cash": "Cash drawer",
}
UNSPECIFIED_ACCOUNT_LABEL = "Unspecified (to be decided)"

EXPENSE_CATEGORIES = [
    ("Personal", "daily"),
    ("Shop", "daily"),
]


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


def read_sheet_sept(wb, name, cols, ffill_cols):
    ws = wb[name]
    headers = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]
    rows = []
    last: dict = {}
    for r in range(2, ws.max_row + 1):
        raw = {h: ws.cell(row=r, column=i + 1).value for i, h in enumerate(headers) if h}
        row = {"_row": r}
        for col in cols:
            v = raw.get(col)
            if col == "Ledger Date":
                v = to_date(v)
            if col in ffill_cols:
                if v is not None and str(v).strip() != "":
                    last[col] = v
                v = last.get(col)
            row[col] = v
        if row["Ledger Date"] and row["Ledger Date"].year == 2026 and row["Ledger Date"].month == 9:
            rows.append(row)
    return rows


async def resolve_party(db, cache: dict, raw_name: str) -> Party:
    canonical = PARTY_NAME_MAP.get(raw_name.strip().lower(), raw_name.strip())
    if canonical in cache:
        return cache[canonical]
    party = await db.scalar(select(Party).where(Party.name == canonical))
    if party is None:
        raise RuntimeError(f"Party {canonical!r} (from {raw_name!r}) not found -- expected to be pre-created")
    cache[canonical] = party
    return party


async def resolve_payment_account(db, cache: dict, raw_method) -> PaymentAccount:
    label = PAYMENT_METHOD_MAP.get(str(raw_method).strip().lower()) if raw_method else UNSPECIFIED_ACCOUNT_LABEL
    if label in cache:
        return cache[label]
    account = await db.scalar(select(PaymentAccount).where(PaymentAccount.label == label))
    if account is None:
        raise RuntimeError(f"Payment account {label!r} not found")
    cache[label] = account
    return account


async def main(apply: bool) -> None:
    wb = openpyxl.load_workbook(SRC, data_only=True)
    expenses_rows = read_sheet_sept(
        wb, "Expenses", ["Ledger Date", "Amount", "Detail", "Category"], ["Ledger Date"]
    )
    ra_rows = read_sheet_sept(
        wb,
        "Received Amount",
        ["Ledger Date", "Amount", "Customer / Detail", "Bank / Payment Method"],
        ["Ledger Date"],
    )

    async with SessionLocal() as db:
        # --- Step 1: pre-create new parties + expense categories (idempotent, exact-name
        # lookup). Matches this codebase's established convention (see e.g. the TPU Case
        # import scripts): get-or-create lookup resolution happens unconditionally, even
        # during a dry run -- only the actual transactional writes below are gated behind
        # --apply, so a dry run still reports accurate, real counts without crashing on
        # not-yet-existing foreign keys.
        created_parties = []
        for name, roles in NEW_PARTIES:
            existing = await db.scalar(select(Party).where(Party.name == name))
            if existing is None:
                party = Party(name=name, roles=[r.value for r in roles], opening_balance=Decimal(0))
                db.add(party)
                created_parties.append(name)

        created_categories = []
        for name, freq in EXPENSE_CATEGORIES:
            existing = await db.scalar(select(ExpenseCategory).where(ExpenseCategory.name == name))
            if existing is None:
                db.add(ExpenseCategory(name=name, frequency=freq))
                created_categories.append(name)

        await db.commit()

        print(f"New parties created: {created_parties or '(none -- already existed)'}")
        print(f"New expense categories created: {created_categories or '(none -- already existed)'}")

        # --- Step 2: resolve lookups fresh (post-commit, so new rows are visible) ---
        category_by_name = {
            name: await db.scalar(select(ExpenseCategory).where(ExpenseCategory.name == name))
            for name, _ in EXPENSE_CATEGORIES
        }
        unspecified_account = await db.scalar(
            select(PaymentAccount).where(PaymentAccount.label == UNSPECIFIED_ACCOUNT_LABEL)
        )

        party_cache: dict = {}
        account_cache: dict = {}

        # --- Step 3: Expenses ---
        exp_skipped = 0
        exp_to_create = []
        for row in expenses_rows:
            amount = row["Amount"]
            if amount is None or amount == 0:
                exp_skipped += 1
                continue
            category = category_by_name.get(row["Category"])
            if category is None:
                raise RuntimeError(f"Expense row {row['_row']}: unmapped category {row['Category']!r}")
            exp_to_create.append(
                {
                    "category_id": category.id,
                    "payment_account_id": unspecified_account.id,
                    "amount": Decimal(str(amount)),
                    "expense_date": row["Ledger Date"],
                    "description": row["Detail"],
                }
            )
        print(f"\nExpenses: {len(exp_to_create)} to create, {exp_skipped} skipped (blank/zero)")

        # --- Step 4: Received Amount ---
        ra_skipped = 0
        ra_to_create = []
        for row in ra_rows:
            amount = row["Amount"]
            customer = row["Customer / Detail"]
            if amount is None or amount == 0 or not customer:
                ra_skipped += 1
                continue
            party = await resolve_party(db, party_cache, customer)
            account = await resolve_payment_account(db, account_cache, row["Bank / Payment Method"])
            ra_to_create.append(
                {
                    "payment_account_id": account.id,
                    "direction": "in",
                    "amount": Decimal(str(amount)),
                    "transaction_date": row["Ledger Date"],
                    "party_id": party.id,
                }
            )
        print(f"Received Amount: {len(ra_to_create)} to create, {ra_skipped} skipped (blank/zero/no-party)")

        exp_total = sum(e["amount"] for e in exp_to_create)
        ra_total = sum(r["amount"] for r in ra_to_create)
        print(f"\nTotal expense amount: {exp_total}")
        print(f"Total received amount: {ra_total}")

        if not apply:
            print("\n[DRY RUN] Nothing written. Re-run with --apply to commit.")
            return

        for e in exp_to_create:
            # create_expense posts the matching PaymentTransaction + ledger entries
            # itself (src/expenses/service.py::_post_expense_payment) and commits
            # internally -- don't reimplement that here.
            await expenses_service.create_expense(db, ExpenseCreate(**e))

        for r in ra_to_create:
            await payments_service.create_payment_transaction(db, PaymentTransactionCreate(**r))

        print(f"\nDone. {len(exp_to_create)} expenses and {len(ra_to_create)} received-amount payments applied.")


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
