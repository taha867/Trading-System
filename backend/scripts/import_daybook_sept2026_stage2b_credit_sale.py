"""STATUS: ALREADY APPLIED TO PRODUCTION (October 2026). DO NOT RE-RUN WITH --apply.
The resume checks below compare invoice numbers that were later corrected in production (the carried-down
invoice numbers were cleared), so a re-run would no longer recognise what it already wrote and would create
DUPLICATE purchases, stock lots, sales and ledger entries. `--apply` therefore refuses to run unless
`--i-understand-this-already-ran-in-production` is also passed. A dry run (no --apply) is still safe.
See PRODUCTION_CHANGES_LOG.md for what was applied and changed afterwards.

Day-book catch-up, Stage 2b: September 2026 Credit Sale rows that DO have a
specific catalog item -- the ~464 rows left after Stage 2a handled everything
that couldn't resolve to a real item (cancelled invoices, bulk/mixed-model
batches, corrections/discounts).

Model strings in this sheet follow a "BRAND/MODEL[/MODEL...]" convention (e.g.
"VIVO/Y15", or "INFINIX/TECNO/HOT11S/CAMMON18" for a cross-brand compatible
group). This script re-derives that same resolution worked out interactively
this session:
  - Brand tokens are recognized by alias (APPLE/IP -> iPhone, SAM -> Samsung, etc).
  - A model token is matched against the EXISTING catalog for every brand
    mentioned in the string first (never positionally) -- this is what caught
    e.g. "HOT50I"/"SMART 9" really being Infinix while "SPARKGO1" in the same
    cell is Tecno, and avoided silently creating duplicate iPhone models (the
    sheet uses "IP13PRO" style abbreviations throughout, which an earlier,
    narrower normalization pass here missed entirely).
  - A handful of multi-brand groups and no-brand tokens needed a human call
    (MANUAL_OVERRIDES below) -- resolved against the Ayan "Compatible Models
    System" reference and the user's own confirmations this session.
  - Lens-protector categories (Jun Best / Simple Lens) encode color as a
    trailing token ("GOLDEN", "BLACKTITANIUM") -- matched against the specific
    Item.variant of whichever model it follows, not treated as another model.
  - Three true duplicate catalog entries (same model name, two Item rows) were
    found and merged by hand before this script was written: Infinix "Note 50"
    (228->241), "IP 14 Pro" (320->898), "IP 13 Pro Max" (899->323). This
    script's catalog lookups already reflect that merge.

Consecutive rows sharing the same (Ledger Date, Customer, Invoice#) become one
SalesOrder with multiple lines, consistent with how the sheet itself groups
"Party Total (this Ledger Date)".

Run with the backend's own venv:
    DATABASE_URL=... backend/.venv/bin/python scripts/import_daybook_sept2026_stage2b_credit_sale.py [--apply]
"""

import argparse
import asyncio
import datetime
import itertools
import os
import re
import sys
from decimal import Decimal

import openpyxl

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
from src.ledger import service as ledger_service
from src.ledger.models import LedgerEntry  # noqa: F401
from src.models import Setting  # noqa: F401
from src.parties.models import Party
from src.payments.models import PaymentAccount, PaymentMethod, PaymentTransaction  # noqa: F401
from src.purchasing.models import ExchangeRate, PurchaseOrder, PurchaseOrderLine  # noqa: F401
from src.sales.models import SalesLogException, SalesOrder, SalesOrderLine, SalesOrderLineLot  # noqa: F401

SRC = "/home/m-taha/Desktop/upwork/shakeel accesories/Daily Cash Book/Daily Cash Book (Sept 2026).xlsx"

CATEGORY_MAP = {
    "OG": "OG Glass Protector", "OG Glass": "OG Glass Protector",
    "OG FINGER PRINT": "OG Finger Protector", "OG Finger Print": "OG Finger Protector",
    "TPU": "TPU Case", "Dust Plug": "Dust Plug", "Dust plug": "Dust Plug",
    "POLISH GLASS": "Polish Glass Protector", "Polish Glass": "Polish Glass Protector",
    "Simple Cam Lens": "Simple Lens Protector", "J.Best Cam Lens": "Jun Best Lens Protector",
    "MEMBRAN SHEET": "Membrane Sheet Protector", "Membrane Sheet": "Membrane Sheet Protector",
    "ItsMe Privacy": "Its Me Privacy Protector", "UV ItsMe Privacy": "Its Me UV Glass Protector",
    "Privacy Glass (Simple)": "Simple Privacy Protector", "MATT PRIVACY J,BEST": "Matt Privacy Glass Protector",
}
BRAND_ALIASES = {
    "APPLE": "iPhone", "IP": "iPhone", "IPHONE": "iPhone",
    "SAMSUNG": "Samsung", "SAM": "Samsung",
    "XIAOMI": "Redmi", "RMI": "Redmi", "MI": "Redmi", "REDMI": "Redmi",
    "REALME": "Realme", "RME": "Realme",
    "INFINIX": "Infinix", "INF": "Infinix",
    "TECNO": "Tecno", "OPPO": "Oppo", "VIVO": "Vivo",
    "ONEPLUS": "OnePlus", "1PLUS": "OnePlus",
    "HUAWEI": "Huawei", "HW": "Huawei", "ITEL": "Itel",
    "PIXEL": "Google Pixel", "GOOGLE": "Google Pixel",
}

# Resolved this session, against the Ayan "Compatible Models System" reference and
# known product-line naming (Infinix Smart/Hot vs Tecno Spark/Camon, Vivo F/V-series).
# Maps the exact sheet model string -> ordered [(brand, model_name), ...]; first entry
# becomes the primary Item, the rest become compatible models on it.
MANUAL_OVERRIDES = {
    ("OG Glass Protector", "INFINIX/TECNO/SMART 9/HOT50I/SPARKGO1"): [
        ("Infinix", "Smart 9"), ("Infinix", "Hot 50i"), ("Tecno", "Spark Go 1"),
    ],
    ("OG Glass Protector", "INFINIX/TECNO/HOT11S/CAMMON18"): [
        ("Infinix", "Hot 11S"), ("Tecno", "Camon 18"),
    ],
    ("OG Glass Protector", "SAMSUNG/VIVO/F15/V20/V21/V21E"): [
        ("Vivo", "F15"), ("Vivo", "V20"), ("Vivo", "V21"), ("Vivo", "V21E"),
    ],
    ("Dust Plug", "Y500"): [("Vivo", "Y500")],
    ("OG Glass Protector", "NILL"): None,  # handled in stage 2a, should never hit this script
    ("OG Glass Protector", "A16"): [("Samsung", "Galaxy A16")],
    ("OG Glass Protector", "A36/A56"): [("Samsung", "Galaxy A36"), ("Samsung", "Galaxy A56")],
    ("OG Finger Protector", "s24 ultra"): [("Samsung", "Galaxy S24 Ultra")],
    ("OG Glass Protector", "13 C"): [("Redmi", "13C")],
    ("OG Glass Protector", "R"): [("iPhone", "iPhone XR")],
    ("OG Glass Protector", "PIXEL 9"): [("Google Pixel", "Pixel 9")],
    ("Dust Plug", "R"): [("iPhone", "iPhone XR")],  # row 3, same invoice/meaning as the OG Glass Protector "R"
    ("Membrane Sheet Protector", "iPhone 17 Pro Max"): [("iPhone", "iPhone 17 Pro Max")],  # no "/" in this cell at all
}

# model_str -> which Item.variant to pick when the matched model has multiple
# variant-split items and the sheet gave no further color token to match against.
VARIANT_OVERRIDES = {
    ("OG Glass Protector", "APPLE/IP6+/IP7+"): "White",
}


def norm(s: str) -> str:
    s = s.upper()
    s = re.sub(r"\bGALAXY\b", "", s)
    s = re.sub(r"\bIPHONE\b", "IP", s)
    s = re.sub(r"[^A-Z0-9+]", "", s)
    return s


def vnorm(v: str) -> str:
    return re.sub(r"[^A-Z]", "", v.upper())


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


PARTY_NAME_MAP = {
    "abdullah mobile mandi bhaudeen": "Abdullah Mobile, Mandi Bhaudeen",
    "dream mobile sargodha": "DREAM MOB SARGODAH",
    "hasan man mobile shekhupura": "Hasan Man, Sheikhupura",
    "jilani mobile d.i khan": "GILLANI MOB DI KHAN",
    "m.h mobile abdul hakeem": "MH MOB ABDULHAKEEM",
    "mobile store khanewal": "Mobile Store, Khanewal",
    "naveed mobile chowk azam": "Naveed Mobile, Chowk Azam",
    "noman mobile multan": "Noman Mobile, Multan",
    "osama mobile arifwala": "OSAMA MOBILE ARIFWALA",
    "s&a": "S&A",
    "shehzad mobilearifwala": "SHAHZAD MB ARIFWALA",
    "shoaib mobile jhang": "Shoaib Mobile, Jhang",
    "sonu traders khawali lakhan": "SONU MOBILE HAVALI LAKKA",
    "waseem mobile mazafargarh": "WASEEM MB MUZAFFARGARH",
}


def read_credit_sale_sept(wb):
    ws = wb["Credit Sale"]
    headers = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]
    rows = []
    last_ledger_date = last_customer = last_invoice = None
    for r in range(2, ws.max_row + 1):
        raw = {h: ws.cell(row=r, column=i + 1).value for i, h in enumerate(headers) if h}
        ld = to_date(raw.get("Ledger Date"))
        if ld is not None:
            last_ledger_date, last_customer, last_invoice = ld, None, None
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
        rows.append({
            "_row": r, "Ledger Date": last_ledger_date, "Amount": raw.get("Amount"),
            "Qty": raw.get("Qty"), "Rate": raw.get("Rate"), "Category": raw.get("Category"),
            "Model": raw.get("Model"), "Customer": cust, "INVOICE#": inv,
            "Comment": raw.get("Comment"),
        })
    return [r for r in rows if r["Ledger Date"] and r["Ledger Date"].year == 2026 and r["Ledger Date"].month == 9]


def is_exception_row(row) -> bool:
    if row["Comment"] == "invoice was cancelled":
        return True
    if row["Category"] in ("Correction", "Discount"):
        return True
    if row["Model"] in ("(Bulk, mixed models)", "NEW", "NILL"):
        return True
    if not row["Qty"] or row["Rate"] is None or not row["Category"]:
        return True
    if not row["Model"]:
        return True
    return False


# Row 3 (invoice 417) has Category genuinely blank in the sheet -- same invoice/line
# group as row 2 (Dust Plug, Y500) ; confirmed resolution: Category=Dust Plug, "R" = iPhone XR.
ROW_OVERRIDES = {
    3: {"Category": "Dust Plug", "Model": "R"},
}


class ResolutionError(Exception):
    pass


async def get_or_create_brand(db, cache, name):
    if name in cache:
        return cache[name]
    brand = await db.scalar(select(Brand).where(Brand.name == name))
    if brand is None:
        raise ResolutionError(f"Brand {name!r} does not exist -- expected all 12 brands to pre-exist")
    cache[name] = brand
    return brand


async def get_or_create_model(db, cache, brand, model_name):
    key = (brand.id, model_name)
    if key in cache:
        return cache[key]
    model = await db.scalar(select(Model).where(Model.brand_id == brand.id, Model.name == model_name))
    if model is None:
        model = Model(brand_id=brand.id, name=model_name, is_active=True)
        db.add(model)
        await db.flush()
    cache[key] = model
    return model


async def get_or_create_item(db, cache, category, model, brand, variant=None):
    key = (category.id, model.id, variant)
    if key in cache:
        return cache[key]
    q = select(Item).where(Item.category_id == category.id, Item.model_id == model.id)
    q = q.where(Item.variant == variant) if variant else q.where(Item.variant.is_(None))
    item = await db.scalar(q)
    if item is None:
        base_sku = (
            f"{category.name[:4].upper()}-{brand.name.upper().replace(' ', '')}"
            f"-{model.name.upper().replace(' ', '')}"
        )
        sku, suffix = base_sku, 1
        while await db.scalar(select(Item).where(Item.sku == sku)) is not None:
            suffix += 1
            sku = f"{base_sku}-{suffix}"
        item = Item(category_id=category.id, model_id=model.id, sku=sku, variant=variant, is_active=True)
        db.add(item)
        await db.flush()
    cache[key] = item
    return item


def resolve_catalog_tokens(sheet_cat, model_str):
    """Returns ordered [(brand_name, model_name_in_catalog_spelling_or_raw, item_variant_or_None), ...]
    for the primary + compatible models of one row. Raises ResolutionError if anything
    is genuinely unresolvable (should never happen for the 270 combos worked out this session)."""
    real_cat = CATEGORY_MAP.get(sheet_cat, sheet_cat)  # sheet_cat may already BE the real name (ROW_OVERRIDES)
    override_key = (real_cat, model_str)
    if override_key in MANUAL_OVERRIDES:
        val = MANUAL_OVERRIDES[override_key]
        if val is None:
            raise ResolutionError(f"{override_key} should have been handled by stage 2a, not this script")
        return real_cat, [(b, m, None) for b, m in val]

    variant_override = VARIANT_OVERRIDES.get(override_key)

    tokens = [t.strip() for t in model_str.split("/")]
    brand_tokens, model_tokens = [], []
    for tok in tokens:
        tok_u = tok.upper().replace(" ", "")
        if tok_u in BRAND_ALIASES and BRAND_ALIASES[tok_u] not in brand_tokens:
            brand_tokens.append(BRAND_ALIASES[tok_u])
        else:
            model_tokens.append(tok)
    if not brand_tokens:
        raise ResolutionError(f"No brand token in {model_str!r} (category {sheet_cat!r})")

    return real_cat, (brand_tokens, model_tokens, variant_override)


async def main(apply: bool) -> None:
    wb = openpyxl.load_workbook(SRC, data_only=True)
    rows = read_credit_sale_sept(wb)
    for row in rows:
        if row["_row"] in ROW_OVERRIDES:
            row.update(ROW_OVERRIDES[row["_row"]])

    real_rows = [r for r in rows if not is_exception_row(r)]
    print(f"Real item-level rows to process: {len(real_rows)}")

    async with SessionLocal() as db:
        # Load the existing catalog once, keyed by (category_name, brand_name) -> {norm(model): (model_row, item_row)}
        categories = {c.name: c for c in (await db.scalars(select(Category))).all()}
        brands = {b.name: b for b in (await db.scalars(select(Brand))).all()}
        catalog_models = (await db.scalars(select(Model))).all()
        models_by_brand = {}
        for m in catalog_models:
            models_by_brand.setdefault(m.brand_id, {})[norm(m.name)] = m
        items_all = (await db.scalars(select(Item))).all()
        # Keyed by (model_id, category_id) -- a Model is shared across categories (one
        # "Vivo Y20" Model row serves OG Glass, Dust Plug, TPU Case, ...), but variant
        # ambiguity only makes sense per actual Item, which is category-scoped.
        items_by_model = {}
        for it in items_all:
            items_by_model.setdefault((it.model_id, it.category_id), []).append(it)

        brand_cache, model_cache, item_cache = {}, {}, {}
        party_cache: dict = {}

        async def resolve_party(raw_name):
            # Invoices #14 and #24 are cash sales to an unnamed walk-in customer (same
            # pattern as #37/Hasan Man Sheikhupura, just with no name recorded at all) --
            # same generic bucket used for Received Amount's "CASH invoice 14"/"Mix" rows.
            if not raw_name:
                canonical = "Cash (Walk-in / Anonymous)"
            else:
                canonical = PARTY_NAME_MAP.get(re.sub(r"\s+", " ", raw_name.strip().lower()), raw_name.strip())
            if canonical in party_cache:
                return party_cache[canonical]
            party = await db.scalar(select(Party).where(Party.name == canonical))
            if party is None:
                raise ResolutionError(f"Party {canonical!r} (from {raw_name!r}) not found")
            party_cache[canonical] = party
            return party

        async def resolve_line_items(sheet_cat, model_str):
            real_cat_name, resolved = resolve_catalog_tokens(sheet_cat, model_str)
            category = categories[real_cat_name]
            result = []  # [(brand_name, model_name, variant), ...]
            if isinstance(resolved, list):
                for brand_name, model_name, variant in resolved:
                    result.append((brand_name, model_name, variant))
            else:
                brand_tokens, model_tokens, variant_override = resolved
                for tok in model_tokens:
                    n = norm(tok)
                    hits = []
                    for brand_name in brand_tokens:
                        brand = brands[brand_name]
                        m = models_by_brand.get(brand.id, {}).get(n)
                        if m:
                            hits.append((brand_name, m))
                    if len(hits) == 1:
                        brand_name, model_row = hits[0]
                        its = items_by_model.get((model_row.id, category.id), [])
                        variant = None
                        if len(its) > 1:
                            if variant_override:
                                variant = variant_override
                            else:
                                # try to match a leftover color token elsewhere in model_tokens
                                for other_tok in model_tokens:
                                    if other_tok is tok:
                                        continue
                                    otn = vnorm(other_tok)
                                    cands = [i.variant for i in its if i.variant and
                                             (vnorm(i.variant) in otn or otn in vnorm(i.variant))]
                                    if len(set(cands)) == 1:
                                        variant = cands[0]
                                if variant is None:
                                    raise ResolutionError(
                                        f"{model_str!r}: model {model_row.name!r} has variants "
                                        f"{[i.variant for i in its]} and no color token to pick one"
                                    )
                        result.append((brand_name, model_row.name, variant))
                    elif len(hits) > 1:
                        raise ResolutionError(f"{model_str!r}: token {tok!r} ambiguous across {hits}")
                    else:
                        if len(brand_tokens) == 1:
                            result.append((brand_tokens[0], tok, None))
                        else:
                            raise ResolutionError(
                                f"{model_str!r}: new model {tok!r}, ambiguous brand among {brand_tokens}"
                            )
            return category, result

        # group consecutive rows into one SalesOrder per (date, customer, invoice#)
        def group_key(r):
            return (r["Ledger Date"], r["Customer"], r["INVOICE#"])

        orders = []
        free_adjustments = []  # zero-rate rows -- real units left the shelf (giveaway/sample), no sale value
        errors = []
        for key, group in itertools.groupby(real_rows, key=group_key):
            group = list(group)
            date, customer, invoice = key
            try:
                party = await resolve_party(customer)
            except ResolutionError as e:
                errors.append((key, str(e)))
                continue
            lines = []
            for row in group:
                try:
                    category, resolved_models = await resolve_line_items(row["Category"], row["Model"])
                except ResolutionError as e:
                    errors.append((row["_row"], str(e)))
                    continue
                primary_brand, primary_model_name, primary_variant = resolved_models[0]
                brand = await get_or_create_brand(db, brand_cache, primary_brand)
                model = await get_or_create_model(db, model_cache, brand, primary_model_name)
                item = await get_or_create_item(db, item_cache, category, model, brand, primary_variant)
                compat_items = []
                for cb, cm, cv in resolved_models[1:]:
                    cbrand = await get_or_create_brand(db, brand_cache, cb)
                    cmodel = await get_or_create_model(db, model_cache, cbrand, cm)
                    compat_items.append((cmodel, cv))
                for cmodel, cv in compat_items:
                    existing = await db.scalar(
                        select(ItemCompatibleModel).where(
                            ItemCompatibleModel.item_id == item.id, ItemCompatibleModel.model_id == cmodel.id
                        )
                    )
                    if existing is None:
                        db.add(ItemCompatibleModel(item_id=item.id, model_id=cmodel.id))
                if row["Rate"] == 0:
                    # Can't be a real SalesOrderLine (rate must be > 0) -- a real unit still
                    # left the shelf though (free/sample per the day book), so it's a stock
                    # adjustment, not a sale.
                    free_adjustments.append({
                        "row": row["_row"], "item": item, "qty": Decimal(str(row["Qty"])),
                        "date": date, "invoice": invoice,
                    })
                    continue
                lines.append({
                    "row": row["_row"], "item": item, "qty": Decimal(str(row["Qty"])),
                    "rate_pkr": Decimal(str(row["Rate"])),
                })
            if lines:
                orders.append({"date": date, "party": party, "invoice": invoice, "lines": lines})

        total_lines = sum(len(o["lines"]) for o in orders)
        total_amount = sum(l["qty"] * l["rate_pkr"] for o in orders for l in o["lines"])
        print(f"Orders to create: {len(orders)}  (total lines: {total_lines}, total amount: {total_amount})")
        print(f"Free/sample stock adjustments (zero-rate rows): {len(free_adjustments)}")
        print(f"Resolution errors: {len(errors)}")
        for e in errors[:30]:
            print("  ERROR:", e)

        if not apply:
            if not errors:
                await db.rollback()
            print("\n[DRY RUN] Nothing written. Re-run with --apply to commit.")
            return
        if errors:
            raise ResolutionError(f"{len(errors)} unresolved rows -- aborting, nothing written")

        for o in orders:
            total_pkr = Decimal(0)
            so = SalesOrder(party_id=o["party"].id, order_date=o["date"],
                             invoice_number=str(o["invoice"]) if o["invoice"] is not None else None)
            db.add(so)
            await db.flush()
            for l in o["lines"]:
                try:
                    consumptions = await inventory_service.consume_stock_fifo(
                        db, item_id=l["item"].id, qty_needed=l["qty"], movement_date=o["date"]
                    )
                except Exception:
                    print(f"FAILED on row {l['row']}: item={l['item'].id} sku={l['item'].sku} "
                          f"qty_needed={l['qty']} date={o['date']} party={o['party'].name} invoice={o['invoice']}")
                    raise
                line = SalesOrderLine(
                    sales_order_id=so.id, item_id=l["item"].id, qty=l["qty"], rate_pkr=l["rate_pkr"],
                )
                db.add(line)
                await db.flush()
                for c in consumptions:
                    db.add(SalesOrderLineLot(
                        sales_order_line_id=line.id, stock_lot_id=c.stock_lot_id,
                        qty_consumed=c.qty_consumed, unit_cost_pkr=c.unit_cost_pkr,
                    ))
                total_pkr += l["qty"] * l["rate_pkr"]
            await ledger_service.post_entry(
                db, entry_date=o["date"], account="Accounts Receivable", debit=total_pkr,
                reference_type="sales_order", reference_id=so.id, party_id=o["party"].id,
            )
            await db.commit()

        for a in free_adjustments:
            qty_needed = a["qty"]
            lots = (await db.scalars(
                select(StockLot).where(StockLot.item_id == a["item"].id, StockLot.qty_remaining > 0)
                .order_by(StockLot.received_date, StockLot.id)
            )).all()
            available = sum((lot.qty_remaining for lot in lots), Decimal(0))
            if available < qty_needed:
                raise ResolutionError(
                    f"Row {a['row']}: free/sample adjustment needs {qty_needed} of item {a['item'].id}, "
                    f"only {available} in stock"
                )
            remaining = qty_needed
            for lot in lots:
                if remaining <= 0:
                    break
                take = min(remaining, lot.qty_remaining)
                lot.qty_remaining -= take
                db.add(StockMovement(
                    stock_lot_id=lot.id, movement_type="damaged", qty_delta=-take,
                    reason=f"Free/sample, zero-rate per day book (invoice #{a['invoice']})",
                    movement_date=a["date"],
                ))
                remaining -= take
            await db.commit()

        print(f"\nDone. {len(orders)} sales orders / {total_lines} lines applied. "
              f"{len(free_adjustments)} free/sample stock adjustments applied.")


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
