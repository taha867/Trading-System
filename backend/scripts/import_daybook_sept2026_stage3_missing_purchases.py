"""Day-book catch-up, Stage 3: September 2026 Local Purchase rows the earlier import skipped.

The Stage 2 (combined) import only kept Local Purchase rows that had BOTH a category and a
model. 56 rows (Rs 536,215) had only one of the two and were dropped without a trace, which
understated supplier balances and left no stock behind for the sales that used it. This
script enters them, using the decisions agreed with the owner:

  Class A -- a model but no category (40 rows, Rs 417,840): category by rate (<= Rs 52 and
            Rs 55-80 -> OG Glass Protector, Rs 90 -> Dust Plug), entered exactly like a Stage 2
            local purchase: one PurchaseOrder + one line (landed cost = rate), an Accounts
            Payable credit, a StockLot and a "receipt" StockMovement. If the sheet's "Sold To"
            column names a buyer, the same quantity is resold at the same rate (a SalesOrder,
            FIFO stock out, Accounts Receivable debit), as Stage 2 did.
  Class B -- a category but no model (16 rows, Rs 118,375): the money owed to the supplier only,
            an Accounts Payable credit with reference_type "local_purchase_exception" and the
            sheet row as reference_id (like the A.Power Traders row), no stock.

Sheet row 21 (A.Power Traders) was already booked by Stage 2 and is excluded.

Default is a READ-ONLY plan (nothing is written, nothing is created). `--rehearse` runs the whole
write path inside one transaction and ALWAYS rolls it back (nothing persists; the only trace is
skipped id numbers, because database sequences are not rolled back). `--apply` does everything in
ONE transaction and checks the totals below before committing; any mismatch rolls it all back.
Refuses to run if any of these purchases already exist (no partial resume).

    DATABASE_URL=postgresql+asyncpg://... backend/.venv/bin/python \
        scripts/import_daybook_sept2026_stage3_missing_purchases.py [--rehearse | --apply]
"""

import argparse
import asyncio
import collections
import datetime
import os
import re
import sys
from dataclasses import dataclass, field
from decimal import Decimal

import openpyxl

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # backend/ on sys.path

from sqlalchemy import func, select

# Every ORM model module must be imported before the first flush/commit.
from src.auth.models import User  # noqa: F401
from src.cargo.models import CargoAllocation, CargoCostBasis, CargoMode, CargoShipment  # noqa: F401
from src.catalog.models import Brand, Category, Item, ItemCompatibleModel, Model
from src.database import SessionLocal
from src.expenses.models import Expense, ExpenseCategory, RecurringExpenseTemplate  # noqa: F401
from src.inventory import service as inventory_service
from src.inventory.models import StockLot, StockMovement
from src.ledger import service as ledger_service
from src.ledger.models import LedgerEntry
from src.models import Setting  # noqa: F401
from src.parties.models import Party
from src.payments.models import PaymentAccount, PaymentMethod, PaymentTransaction  # noqa: F401
from src.purchasing.models import ExchangeRate, PurchaseOrder, PurchaseOrderLine  # noqa: F401
from src.sales.models import SalesLogException, SalesOrder, SalesOrderLine, SalesOrderLineLot  # noqa: F401

SRC = "/home/m-taha/Desktop/upwork/shakeel accesories/Daily Cash Book/Daily Cash Book (Sept 2026).xlsx"
SEPT = (datetime.date(2026, 9, 1), datetime.date(2026, 9, 30))
ALREADY_BOOKED_ROW = 21  # A.Power Traders -- booked by Stage 2 as a local_purchase_exception

# What the owner approved. --apply aborts (rolls back) unless the data produces exactly this.
EXPECTED = {
    "a_rows": 40, "a_amount": Decimal("417840"),
    "b_rows": 16, "b_amount": Decimal("118375"),
    "resale_rows": 9, "resale_amount": Decimal("8380"),
}

CATEGORY_OG, CATEGORY_DUST = "OG Glass Protector", "Dust Plug"

# Sheet shorthand -> [(brand, model name)]. The first entry is the primary model; the rest are
# recorded as compatible models on the same item (same convention as Stage 2). Decisions
# confirmed by the owner: A80 = Samsung, C51 = Realme, A6 = Oppo, A6c = Oppo.
MODEL_SPECS = {
    "Iphone X": [("iPhone", "iPhone X")], "Iphone 12 pro": [("iPhone", "iPhone 12 Pro")],
    "iphone 15": [("iPhone", "iPhone 15")], "13 pro": [("iPhone", "iPhone 13 Pro")],
    "16 pro max": [("iPhone", "iPhone 16 Pro Max")], "Cammon 20": [("Tecno", "Camon 20")],
    "cammon 30": [("Tecno", "Camon 30")], "Mi note 15": [("Redmi", "Note 15")],
    "pixel 9/ 9 pro": [("Google Pixel", "Pixel 9"), ("Google Pixel", "Pixel 9PRO")],
    "pixel 7": [("Google Pixel", "Pixel 7")], "hot 60 pro": [("Infinix", "HOT 60 PRO")],
    "Pova2/Note7": [("Tecno", "Pova 2"), ("Infinix", "Note 7")], "A32": [("Samsung", "Galaxy A32")],
    "A16": [("Samsung", "Galaxy A16")], "A70": [("Samsung", "Galaxy A70")],
    "Smart 20": [("Infinix", "Smart 20")], "smart 20": [("Infinix", "Smart 20")],
    "Smart 9": [("Infinix", "SMART 9")], "HOT 9": [("Infinix", "Hot 9")], "HOT 10": [("Infinix", "Hot 10")],
    "Hot 10": [("Infinix", "Hot 10")], "Note 50": [("Infinix", "Note50")], "13C": [("Redmi", "13C")],
    "y500": [("Vivo", "Y500")], "v70": [("Vivo", "V70")], "v70 FE": [("Vivo", "V70FE")],
    "A80": [("Samsung", "A80")], "A80/ Note 9s": [("Samsung", "A80"), ("Redmi", "Note 9S")],
    "C51": [("Realme", "C51")], "A6": [("Oppo", "A6")], "A6c": [("Oppo", "A6c")],
    "A3s": [("Oppo", "A3S")], "Oppo Reno 6": [("Oppo", "RENO6")], "Y12/ Y15": [("Vivo", "Y15"), ("Vivo", "Y12")],
}
SUPPLIER_NAMES = {
    "galaxy mobile kamran": "Galaxy Mobile, Kamran", "s&a": "S&A", "alnafeh traders": "AlNafeh Traders",
    "javed traders": "Javed Traders", "ns traders": "NS Traders", "amt": "AMT",
}
BUYER_NAMES = {"habib mobile jhang": "Shoaib Mobile, Jhang", "dream mobile": "DREAM MOB SARGODAH"}


class PlanError(Exception):
    pass


def norm(s) -> str:
    s = re.sub(r"[^a-z0-9]", "", str(s or "").lower()).replace("iphone", "ip")
    for word in ("galaxy", "redmi", "infinix", "samsung", "vivo", "oppo", "tecno", "realme", "google", "pixel"):
        s = s.replace(word, "")
    return s


def to_date(v):
    if v is None:
        return None
    if isinstance(v, datetime.datetime):
        return v.date()
    s = str(v).strip()
    for fmt in ("%d-%m-%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def dec(v) -> Decimal:
    return Decimal(str(v))


def category_for(rate: Decimal) -> str:
    return CATEGORY_DUST if rate == 90 else CATEGORY_OG  # <= 52 and 55-80 -> OG Glass (owner's default)


def clean_name(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).strip().lower())


@dataclass
class Row:
    sheet_row: int
    date: datetime.date
    supplier: str
    invoice: str | None
    category: str | None
    model: str | None
    qty: Decimal
    rate: Decimal
    sold_to: str | None

    @property
    def amount(self) -> Decimal:
        return self.qty * self.rate


@dataclass
class Plan:
    row: Row
    kind: str  # "A" (stock) | "B" (payable only)
    category: str | None = None
    primary: tuple | None = None  # (brand, model name)
    model: Model | None = None  # existing model, or None -> create
    item: Item | None = None  # existing item, or None -> create
    compat: list = field(default_factory=list)  # [(brand, name, Model | None)]
    notes: list = field(default_factory=list)  # human-readable things that would be created / chosen


def read_missing_rows(wb) -> list[Row]:
    """Local Purchase rows (September ledger dates) that Stage 2 skipped: no category or no model."""
    ws = wb["Local Purchase"]
    headers = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]
    rows, ld, sup, inv, sold = [], None, None, None, None
    for r in range(2, ws.max_row + 1):
        raw = {h: ws.cell(row=r, column=i + 1).value for i, h in enumerate(headers) if h}
        new_ld = to_date(raw.get("Ledger Date"))
        if new_ld:
            ld, sup, inv, sold = new_ld, None, None, None
        if raw.get("Supplier") not in (None, ""):
            sup = str(raw["Supplier"])
        if raw.get("Invoice #") not in (None, ""):
            if str(raw["Invoice #"]) != str(inv):
                sold = None  # a new invoice has its own buyer; never inherit the previous one's
            inv = raw["Invoice #"]
        if raw.get("Sold To (Party)") not in (None, ""):
            sold = str(raw["Sold To (Party)"])
        if not (ld and SEPT[0] <= ld <= SEPT[1]):
            continue
        amount, qty, rate = raw.get("Amount"), raw.get("Qty"), raw.get("Rate")
        if amount in (None, "") or dec(amount) == 0 or r == ALREADY_BOOKED_ROW:
            continue
        category, model = raw.get("Category"), raw.get("Model")
        if qty and rate is not None and category and model:
            continue  # a complete row: Stage 2 already entered it
        rows.append(Row(r, ld, sup or "", str(inv) if inv is not None else None, category, model, dec(qty), dec(rate), sold))
    return rows


async def build_plans(db, rows: list[Row]) -> list[Plan]:
    categories = {c.name: c for c in (await db.scalars(select(Category))).all()}
    brands = {b.name: b for b in (await db.scalars(select(Brand))).all()}
    models = (await db.scalars(select(Model).where(Model.is_active.is_(True)))).all()
    items = (await db.scalars(select(Item).where(Item.is_active.is_(True)))).all()
    stock = {
        item_id: qty for item_id, qty in (await db.execute(
            select(StockLot.item_id, func.coalesce(func.sum(StockLot.qty_remaining), 0)).group_by(StockLot.item_id)
        )).all()
    }
    by_brand_norm = collections.defaultdict(list)
    for m in models:
        by_brand_norm[(m.brand_id, norm(m.name))].append(m)
    items_by = collections.defaultdict(list)
    for it in items:
        items_by[(it.model_id, it.category_id)].append(it)
    stock_of = lambda its: sum((stock.get(i.id, Decimal(0)) for i in its), Decimal(0))

    plans = []
    for row in rows:
        if row.category and not row.model:
            plans.append(Plan(row=row, kind="B"))
            continue

        category = categories[category_for(row.rate)]
        spec = MODEL_SPECS.get(str(row.model).strip())
        if spec is None:
            raise PlanError(f"Sheet row {row.sheet_row}: model {row.model!r} has no mapping in MODEL_SPECS")

        resolved = []  # (brand_name, model_name, Model | None, [Item])
        notes = []
        for brand_name, model_name in spec:
            if brand_name not in brands:
                raise PlanError(f"Sheet row {row.sheet_row}: brand {brand_name!r} not in the catalog")
            candidates = by_brand_norm.get((brands[brand_name].id, norm(model_name)), [])
            with_items = [m for m in candidates if items_by.get((m.id, category.id))]
            if with_items:
                model = max(with_items, key=lambda m: stock_of(items_by[(m.id, category.id)]))
                if len(with_items) > 1:
                    notes.append(f"{brand_name} {model_name}: {len(with_items)} duplicate models with {category.name} items; chose #{model.id} (most stock)")
            else:
                model = candidates[0] if candidates else None
            its = items_by.get((model.id, category.id), []) if model else []
            if len(its) > 1:
                best = max(its, key=lambda i: stock.get(i.id, Decimal(0)))
                notes.append(f"{brand_name} {model_name}: {len(its)} items; chose #{best.id} {best.sku} (most stock)")
                its = [best]
            resolved.append((brand_name, model_name, model, its))

        primary = next((t for t in resolved if len(t[3]) == 1), resolved[0])
        brand_name, model_name, model, its = primary
        plan = Plan(row=row, kind="A", category=category.name, primary=(brand_name, model_name), model=model, item=its[0] if its else None)
        plan.compat = [(b, n, m) for b, n, m, _i in resolved if (b, n) != (brand_name, model_name)]
        if model is None:
            notes.append(f"CREATE model {brand_name} {model_name}")
        if plan.item is None:
            notes.append(f"CREATE {category.name} item for {brand_name} {model_name}")
        for b, n, m in plan.compat:
            if m is None:
                notes.append(f"CREATE compatible model {b} {n}")
        plan.notes = notes
        plans.append(plan)
    return plans


def summarize(plans: list[Plan]) -> dict:
    a = [p for p in plans if p.kind == "A"]
    b = [p for p in plans if p.kind == "B"]
    resales = [p for p in a if p.row.sold_to]
    return {
        "a_rows": len(a), "a_amount": sum((p.row.amount for p in a), Decimal(0)),
        "b_rows": len(b), "b_amount": sum((p.row.amount for p in b), Decimal(0)),
        "resale_rows": len(resales), "resale_amount": sum((p.row.amount for p in resales), Decimal(0)),
    }


def print_plan(plans: list[Plan], totals: dict) -> None:
    print(f"\nClass A (stock):        {totals['a_rows']:>3} rows  Rs {totals['a_amount']:>10,.0f}")
    print(f"Class B (payable only): {totals['b_rows']:>3} rows  Rs {totals['b_amount']:>10,.0f}")
    print(f"Resales to create:      {totals['resale_rows']:>3} rows  Rs {totals['resale_amount']:>10,.0f}")
    per_supplier = collections.defaultdict(Decimal)
    for p in plans:
        per_supplier[p.row.supplier] += p.row.amount
    print("\nAdded to supplier payables:")
    for name, amount in sorted(per_supplier.items(), key=lambda kv: -kv[1]):
        print(f"  {name:28} Rs {amount:>10,.0f}")
    creates = [(p.row.sheet_row, n) for p in plans for n in p.notes]
    print("\nCatalog creations / choices:")
    for sheet_row, note in creates:
        print(f"  row {sheet_row}: {note}")
    if not creates:
        print("  (none)")


async def apply_plans(db, plans: list[Plan], totals: dict) -> None:
    categories = {c.name: c for c in (await db.scalars(select(Category))).all()}
    brands = {b.name: b for b in (await db.scalars(select(Brand))).all()}

    async def party(raw_name: str, names: dict) -> Party:
        canonical = names.get(clean_name(raw_name), raw_name.strip())
        found = await db.scalar(select(Party).where(Party.name == canonical))
        if found is None:
            raise PlanError(f"Party {canonical!r} (from {raw_name!r}) not found")
        return found

    async def ensure_model(brand_name: str, model_name: str, existing: Model | None) -> Model:
        if existing is not None:
            return existing
        found = await db.scalar(select(Model).where(Model.brand_id == brands[brand_name].id, Model.name == model_name))
        if found is not None:
            return found
        model = Model(brand_id=brands[brand_name].id, name=model_name, is_active=True)
        db.add(model)
        await db.flush()
        return model

    async def ensure_item(plan: Plan) -> Item:
        if plan.item is not None:
            return plan.item
        brand_name, model_name = plan.primary
        model = await ensure_model(brand_name, model_name, plan.model)
        category = categories[plan.category]
        existing = await db.scalar(select(Item).where(Item.category_id == category.id, Item.model_id == model.id, Item.variant.is_(None)))
        if existing is not None:
            return existing
        base_sku = f"{category.name[:4].upper()}-{brands[brand_name].name.upper().replace(' ', '')}-{model.name.upper().replace(' ', '')}"
        sku, suffix = base_sku, 1
        while await db.scalar(select(Item).where(Item.sku == sku)) is not None:
            suffix += 1
            sku = f"{base_sku}-{suffix}"
        item = Item(category_id=category.id, model_id=model.id, sku=sku, variant=None, is_active=True)
        db.add(item)
        await db.flush()
        return item

    # Idempotency: refuse to run twice (no partial resume -- everything is one transaction).
    for plan in plans:
        row = plan.row
        supplier = await party(row.supplier, SUPPLIER_NAMES)
        if plan.kind == "B":
            clash = await db.scalar(select(LedgerEntry).where(
                LedgerEntry.reference_type == "local_purchase_exception", LedgerEntry.reference_id == row.sheet_row))
        elif plan.item is None:
            clash = None  # its item doesn't exist yet, so nothing can have been entered against it
        else:
            # Same supplier, date, invoice, ITEM, qty and rate. (Qty alone isn't enough: one invoice can
            # carry several lines with the same quantity, e.g. sheet rows 35 and 37 are both "2 x 90".)
            clash = await db.scalar(
                select(PurchaseOrder).join(PurchaseOrderLine).where(
                    PurchaseOrder.party_id == supplier.id, PurchaseOrder.order_date == row.date,
                    PurchaseOrder.source == "local", PurchaseOrder.invoice_number == row.invoice,
                    PurchaseOrderLine.item_id == plan.item.id, PurchaseOrderLine.qty == row.qty,
                    PurchaseOrderLine.rate_pkr == row.rate,
                )
            )
        if clash is not None:
            raise PlanError(f"Sheet row {row.sheet_row} already appears to be entered -- aborting, nothing written")

    payable_total = Decimal(0)
    receivable_total = Decimal(0)
    po_count = so_count = 0
    for plan in sorted(plans, key=lambda p: (p.row.date, p.row.sheet_row)):
        row = plan.row
        supplier = await party(row.supplier, SUPPLIER_NAMES)

        if plan.kind == "B":
            await ledger_service.post_entry(
                db, entry_date=row.date, account="Accounts Payable", credit=row.amount,
                reference_type="local_purchase_exception", reference_id=row.sheet_row, party_id=supplier.id,
            )
            payable_total += row.amount
            continue

        item = await ensure_item(plan)
        for brand_name, model_name, existing in plan.compat:
            compat_model = await ensure_model(brand_name, model_name, existing)
            link = await db.scalar(select(ItemCompatibleModel).where(
                ItemCompatibleModel.item_id == item.id, ItemCompatibleModel.model_id == compat_model.id))
            if link is None:
                db.add(ItemCompatibleModel(item_id=item.id, model_id=compat_model.id))

        po = PurchaseOrder(party_id=supplier.id, order_date=row.date, source="local", status="allocated", invoice_number=row.invoice)
        db.add(po)
        await db.flush()
        line = PurchaseOrderLine(
            purchase_order_id=po.id, item_id=item.id, qty=row.qty, rate_rmb=None, rate_pkr=row.rate, landed_cost_pkr=row.rate,
        )
        db.add(line)
        await db.flush()
        await ledger_service.post_entry(
            db, entry_date=row.date, account="Accounts Payable", credit=row.amount,
            reference_type="purchase_order", reference_id=po.id, party_id=supplier.id,
        )
        lot = StockLot(
            purchase_order_line_id=line.id, item_id=item.id, qty_received=row.qty, qty_remaining=row.qty,
            landed_cost_pkr=row.rate, received_date=row.date,
        )
        db.add(lot)
        await db.flush()
        db.add(StockMovement(stock_lot_id=lot.id, movement_type="receipt", qty_delta=row.qty, reason=None, movement_date=row.date))
        po.status = "received"
        payable_total += row.amount
        po_count += 1

        if row.sold_to:
            buyer = await party(row.sold_to, BUYER_NAMES)
            so = SalesOrder(party_id=buyer.id, order_date=row.date, invoice_number=row.invoice)
            db.add(so)
            await db.flush()
            consumptions = await inventory_service.consume_stock_fifo(db, item_id=item.id, qty_needed=row.qty, movement_date=row.date)
            sale_line = SalesOrderLine(sales_order_id=so.id, item_id=item.id, qty=row.qty, rate_pkr=row.rate)
            db.add(sale_line)
            await db.flush()
            for c in consumptions:
                db.add(SalesOrderLineLot(sales_order_line_id=sale_line.id, stock_lot_id=c.stock_lot_id, qty_consumed=c.qty_consumed, unit_cost_pkr=c.unit_cost_pkr))
            await ledger_service.post_entry(
                db, entry_date=row.date, account="Accounts Receivable", debit=row.amount,
                reference_type="sales_order", reference_id=so.id, party_id=buyer.id,
            )
            receivable_total += row.amount
            so_count += 1

    # Final guard, still inside the transaction: the result must be exactly what was approved.
    expected_payable = totals["a_amount"] + totals["b_amount"]
    problems = []
    if po_count != EXPECTED["a_rows"]:
        problems.append(f"purchase orders {po_count} != {EXPECTED['a_rows']}")
    if so_count != EXPECTED["resale_rows"]:
        problems.append(f"sales orders {so_count} != {EXPECTED['resale_rows']}")
    if payable_total != expected_payable or payable_total != EXPECTED["a_amount"] + EXPECTED["b_amount"]:
        problems.append(f"payable {payable_total} != {EXPECTED['a_amount'] + EXPECTED['b_amount']}")
    if receivable_total != EXPECTED["resale_amount"]:
        problems.append(f"receivable {receivable_total} != {EXPECTED['resale_amount']}")
    if problems:
        raise PlanError("Final check failed, rolling back: " + "; ".join(problems))
    print(f"\nFinal check passed: {po_count} purchase orders, {so_count} sales orders, payable +Rs {payable_total:,.0f}, receivable +Rs {receivable_total:,.0f}")


async def main(apply: bool, rehearse: bool) -> None:
    wb = openpyxl.load_workbook(SRC, data_only=True)
    rows = read_missing_rows(wb)
    print(f"Local Purchase rows missing from the app: {len(rows)}")
    async with SessionLocal() as db:
        plans = await build_plans(db, rows)
        totals = summarize(plans)
        print_plan(plans, totals)
        mismatches = [f"{k}: {totals[k]} != {v}" for k, v in EXPECTED.items() if totals[k] != v]
        if mismatches:
            raise PlanError("Plan does not match what was approved: " + "; ".join(mismatches))
        print("\nPlan matches the approved numbers exactly.")
        if not apply and not rehearse:
            await db.rollback()
            print("[PLAN ONLY] Nothing was written. Re-run with --rehearse to test the write, or --apply to write it.")
            return
        try:
            await apply_plans(db, plans, totals)
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
