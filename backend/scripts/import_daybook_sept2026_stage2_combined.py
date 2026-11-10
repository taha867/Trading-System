"""STATUS: ALREADY APPLIED TO PRODUCTION (October 2026). DO NOT RE-RUN WITH --apply.
The resume checks below compare invoice numbers that were later corrected in production (the carried-down
invoice numbers were cleared), so a re-run would no longer recognise what it already wrote and would create
DUPLICATE purchases, stock lots, sales and ledger entries. `--apply` therefore refuses to run unless
`--i-understand-this-already-ran-in-production` is also passed. A dry run (no --apply) is still safe.
See PRODUCTION_CHANGES_LOG.md for what was applied and changed afterwards.

Day-book catch-up, Stage 2 (final, combined): every September 2026 Local
Purchase and Credit Sale row that has a specific catalog item, processed
together in strict chronological order.

Why combined, not two separate passes: several Credit Sale rows draw on stock
that only exists because of a same-day Local Purchase row (e.g. invoice #417 --
S&A sells Shakeel 20 Vivo Y500 units, which go straight to Sonu Traders the same
day). Running Credit Sale alone hits real "insufficient stock" errors on day
one. Running Local Purchase first, then Credit Sale, in date order, is what
actually matches how the business worked.

This assumes Local Purchase rows are received before Credit Sale rows on the
same Ledger Date (true for every same-day pair found this session) and is
intentionally conservative about resolving every row to a real customer/item --
see MANUAL_OVERRIDES / LOCAL_PURCHASE_OVERRIDES for everything that needed a
human call this session (Ayan reference lookups, product-line naming, merged
duplicate models, color-variant picks).

Exceptions already handled in prior scripts (NOT reprocessed here):
  - Stage 2a: cancelled invoices, bulk/mixed-model Credit Sale rows, corrections/
    discounts, "NEW"/"NILL" model placeholders.
  - This script's own LOCAL_PURCHASE_EXCEPTION: the one Local Purchase row (21,
    A.Power Traders, "Membrane", resold to Dream Mobile) with no resolvable
    model and no given resale amount -- logged as a straight Accounts Payable
    entry, no stock effect, no matching sale (the source gives no sale amount).

Local Purchase's "Sold To (Party)" column means the same physical units were
immediately resold same-day -- each such row generates both the purchase (stock
in) and a matching Credit-Sale-equivalent sale (stock out) in this one script.

Run with the backend's own venv:
    DATABASE_URL=... backend/.venv/bin/python scripts/import_daybook_sept2026_stage2_combined.py [--apply]
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

from sqlalchemy import func, select

# Every ORM model module must be imported before the first flush/commit.
from src.auth.models import User  # noqa: F401
from src.cargo.models import CargoAllocation, CargoCostBasis, CargoMode, CargoShipment  # noqa: F401
from src.catalog.models import Brand, Category, Item, ItemCompatibleModel, Model
from src.database import SessionLocal
from src.expenses.models import Expense, ExpenseCategory, RecurringExpenseTemplate  # noqa: F401
from src.inventory import service as inventory_service
from src.inventory.exceptions import InsufficientStock
from src.inventory.models import StockLot, StockMovement
from src.ledger import service as ledger_service
from src.ledger.models import LedgerEntry  # noqa: F401
from src.models import Setting  # noqa: F401
from src.parties.constants import PartyRole
from src.parties.models import Party
from src.payments.models import PaymentAccount, PaymentMethod, PaymentTransaction  # noqa: F401
from src.purchasing.models import ExchangeRate, PurchaseOrder, PurchaseOrderLine
from src.sales.models import SalesLogException, SalesOrder, SalesOrderLine, SalesOrderLineLot  # noqa: F401

SRC = "/home/m-taha/Desktop/upwork/shakeel accesories/Daily Cash Book/Daily Cash Book (Sept 2026).xlsx"

CATEGORY_MAP = {
    "OG": "OG Glass Protector", "OG Glass": "OG Glass Protector",
    "OG FINGER PRINT": "OG Finger Protector", "OG Finger Print": "OG Finger Protector",
    "TPU": "TPU Case", "Dust Plug": "Dust Plug", "Dust plug": "Dust Plug",
    "POLISH GLASS": "Polish Glass Protector", "Polish Glass": "Polish Glass Protector",
    "Simple Cam Lens": "Simple Lens Protector", "J.Best Cam Lens": "Jun Best Lens Protector",
    "MEMBRAN SHEET": "Membrane Sheet Protector", "Membrane Sheet": "Membrane Sheet Protector",
    "Membrane": "Membrane Sheet Protector",
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

# Credit Sale "/"-formatted rows resolved this session against the Ayan "Compatible
# Models System" reference + known product-line naming. Keyed by (real category, exact
# sheet model string); value is ordered [(brand, model_name), ...] -- first = primary.
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
    ("OG Glass Protector", "A16"): [("Samsung", "Galaxy A16")],
    ("OG Glass Protector", "A36/A56"): [("Samsung", "Galaxy A36"), ("Samsung", "Galaxy A56")],
    ("OG Finger Protector", "s24 ultra"): [("Samsung", "Galaxy S24 Ultra")],
    ("OG Glass Protector", "13 C"): [("Redmi", "13C")],
    ("OG Glass Protector", "R"): [("iPhone", "iPhone XR")],
    ("OG Glass Protector", "PIXEL 9"): [("Google Pixel", "Pixel 9")],
    ("Dust Plug", "R"): [("iPhone", "iPhone XR")],
    ("Membrane Sheet Protector", "iPhone 17 Pro Max"): [("iPhone", "iPhone 17 Pro Max")],
}

# Local Purchase rows are bare model names with no brand token at all -- resolved this
# session against the real catalog + obvious naming (an "iphone 12" row names its own
# brand; "Hot 10"/"Camon 30" are brand-specific product lines; "y20"/"v20"/"S26 ultra"/
# "13 pro max"/"XS"/"A70"/"A26" were checked directly against what already exists).
LOCAL_PURCHASE_OVERRIDES = {
    ("Dust Plug", "y500"): [("Vivo", "Y500")],
    ("Dust Plug", "R"): [("iPhone", "iPhone XR")],
    ("OG Glass Protector", "Hot 10"): [("Infinix", "Hot 10")],
    ("OG Glass Protector", "cammon 30"): [("Tecno", "Camon 30")],
    ("OG Glass Protector", "v20"): [("Vivo", "V20")],
    ("OG Glass Protector", "V20"): [("Vivo", "V20")],
    ("OG Glass Protector", "IP X| XS"): [("iPhone", "iPhone X"), ("iPhone", "iPhone XS")],
    ("OG Glass Protector", "y20"): [("Vivo", "Y20")],
    ("OG Glass Protector", "Y20"): [("Vivo", "Y20")],
    ("OG Glass Protector", "XS"): [("iPhone", "iPhone XS")],
    ("Dust Plug", "C51"): [("Realme", "C51")],
    ("OG Glass Protector", "A26"): [("Samsung", "Galaxy A26")],
    ("OG Glass Protector", "13 pro max"): [("iPhone", "iPhone 13 Pro Max")],
    ("OG Glass Protector", "A70"): [("Samsung", "Galaxy A70")],
    ("OG Glass Protector", "Smart20"): [("Infinix", "Smart 20")],
    ("OG Glass Protector", "Smart 20"): [("Infinix", "Smart 20")],
    ("OG Glass Protector", "iphone 12"): [("iPhone", "iPhone 12")],
    ("OG Glass Protector", "iphone 13 pro max"): [("iPhone", "iPhone 13 Pro Max")],
    ("Dust Plug", "S26 ultra"): [("Samsung", "Galaxy S26 Ultra")],
    ("Membrane Sheet Protector", "iPhone 13"): [("iPhone", "iPhone 13")],
    ("Membrane Sheet Protector", "iPhone 13 Pro"): [("iPhone", "iPhone 13 Pro")],
    ("Membrane Sheet Protector", "iPhone 13 Pro Max"): [("iPhone", "iPhone 13 Pro Max")],
    ("OG Glass Protector", "iphone 12/12 pro"): [("iPhone", "iPhone 12"), ("iPhone", "iPhone 12 Pro")],
}

VARIANT_OVERRIDES = {
    ("OG Glass Protector", "APPLE/IP6+/IP7+"): "White",
}

PARTY_NAME_MAP = {
    "abdullah mobile mandi bhaudeen": "Abdullah Mobile, Mandi Bhaudeen",
    "dream mobile sargodha": "DREAM MOB SARGODAH",
    "dream mobile": "DREAM MOB SARGODAH",
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
    "habib mobile jhang": "Shoaib Mobile, Jhang",
    "sonu traders khawali lakhan": "SONU MOBILE HAVALI LAKKA",
    "waseem mobile mazafargarh": "WASEEM MB MUZAFFARGARH",
    "alnafeh traders": "AlNafeh Traders",
    "javed traders": "Javed Traders",
    "ns traders": "NS Traders",
    "galaxy mobile kamran": "Galaxy Mobile, Kamran",
    "amt": "AMT",
    "a.power traders": "A.Power Traders",
}
NEW_PARTIES = [
    ("S&A", [PartyRole.CUSTOMER, PartyRole.LOCAL_VENDOR]),
    ("AlNafeh Traders", [PartyRole.LOCAL_VENDOR]),
    ("Javed Traders", [PartyRole.LOCAL_VENDOR]),
    ("NS Traders", [PartyRole.LOCAL_VENDOR]),
    ("Galaxy Mobile, Kamran", [PartyRole.LOCAL_VENDOR]),
    ("AMT", [PartyRole.LOCAL_VENDOR]),
    ("A.Power Traders", [PartyRole.LOCAL_VENDOR]),
]


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


def read_local_purchase_sept(wb):
    ws = wb["Local Purchase"]
    headers = [ws.cell(row=1, column=c).value for c in range(1, ws.max_column + 1)]
    rows = []
    last_ledger_date = last_invoice_date = last_invoice = last_supplier = None
    for r in range(2, ws.max_row + 1):
        raw = {h: ws.cell(row=r, column=i + 1).value for i, h in enumerate(headers) if h}
        ld = to_date(raw.get("Ledger Date"))
        if ld is not None:
            last_ledger_date = ld
        inv_date = to_date(raw.get("Invoice Date"))
        if inv_date is not None:
            last_invoice_date = inv_date
        inv = raw.get("Invoice #")
        if inv is not None and str(inv).strip() != "":
            last_invoice = inv
        else:
            inv = last_invoice
        supplier = raw.get("Supplier")
        if supplier is not None and str(supplier).strip() != "":
            last_supplier = supplier
        else:
            supplier = last_supplier
        rows.append({
            "_row": r, "Ledger Date": last_ledger_date, "Invoice Date": last_invoice_date,
            "Invoice #": inv, "Supplier": supplier, "Category": raw.get("Category"),
            "Model": raw.get("Model"), "Qty": raw.get("Qty"), "Rate": raw.get("Rate"),
            "Sold To (Party)": raw.get("Sold To (Party)"),
        })
    return [r for r in rows if r["Ledger Date"] and r["Ledger Date"].year == 2026 and r["Ledger Date"].month == 9]


def is_credit_sale_exception_row(row) -> bool:
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
# group as row 2 (Dust Plug, Y500) ; confirmed: Category=Dust Plug, "R" = iPhone XR.
ROW_OVERRIDES = {3: {"Category": "Dust Plug", "Model": "R"}}

LOCAL_PURCHASE_EXCEPTION_ROW = 21  # A.Power Traders, "Membrane", no resolvable model, no sale amount


class ResolutionError(Exception):
    pass


async def main(apply: bool) -> None:
    wb = openpyxl.load_workbook(SRC, data_only=True)

    cs_rows = read_credit_sale_sept(wb)
    for row in cs_rows:
        if row["_row"] in ROW_OVERRIDES:
            row.update(ROW_OVERRIDES[row["_row"]])
    cs_real = [r for r in cs_rows if not is_credit_sale_exception_row(r)]
    # Every invoice# that appears anywhere in Credit Sale (real or exception row) --
    # a Local Purchase "Sold To" resale under one of these invoice numbers is the SAME
    # physical transaction Shakeel also wrote up as its own Credit Sale entry (confirmed
    # for #417 and #445 earlier this session), so it must NOT also generate a synthetic
    # sale here -- that would consume/bill the same units twice.
    cs_invoice_numbers = {str(r["INVOICE#"]) for r in cs_rows if r["INVOICE#"] is not None}

    lp_rows = read_local_purchase_sept(wb)
    lp_real = [r for r in lp_rows if r["_row"] != LOCAL_PURCHASE_EXCEPTION_ROW and r["Qty"] and r["Rate"] is not None and r["Category"] and r["Model"]]
    lp_exception = next(r for r in lp_rows if r["_row"] == LOCAL_PURCHASE_EXCEPTION_ROW)

    print(f"Credit Sale real rows: {len(cs_real)}, Local Purchase real rows: {len(lp_real)}")

    async with SessionLocal() as db:
        categories = {c.name: c for c in (await db.scalars(select(Category))).all()}
        brands = {b.name: b for b in (await db.scalars(select(Brand))).all()}
        catalog_models = (await db.scalars(select(Model))).all()
        models_by_brand = {}
        for m in catalog_models:
            models_by_brand.setdefault(m.brand_id, {})[norm(m.name)] = m
        items_all = (await db.scalars(select(Item))).all()
        items_by_model = {}
        for it in items_all:
            items_by_model.setdefault((it.model_id, it.category_id), []).append(it)

        brand_cache, model_cache, item_cache = {}, {}, {}
        party_cache: dict = {}

        created_parties = []
        for name, roles in NEW_PARTIES:
            existing = await db.scalar(select(Party).where(Party.name == name))
            if existing is None:
                db.add(Party(name=name, roles=[r.value for r in roles], opening_balance=Decimal(0)))
                created_parties.append(name)
        await db.commit()
        print(f"New parties created: {created_parties or '(none -- already existed)'}")

        async def resolve_party(raw_name):
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

        async def get_or_create_brand(name):
            if name in brand_cache:
                return brand_cache[name]
            brand = brands.get(name)
            if brand is None:
                raise ResolutionError(f"Brand {name!r} does not exist")
            brand_cache[name] = brand
            return brand

        async def get_or_create_model(brand, model_name):
            key = (brand.id, model_name)
            if key in model_cache:
                return model_cache[key]
            model = models_by_brand.get(brand.id, {}).get(norm(model_name))
            if model is None:
                model = await db.scalar(select(Model).where(Model.brand_id == brand.id, Model.name == model_name))
            if model is None:
                model = Model(brand_id=brand.id, name=model_name, is_active=True)
                db.add(model)
                await db.flush()
                models_by_brand.setdefault(brand.id, {})[norm(model_name)] = model
            model_cache[key] = model
            return model

        async def get_or_create_item(category, model, brand, variant=None):
            key = (category.id, model.id, variant)
            if key in item_cache:
                return item_cache[key]
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
                items_by_model.setdefault((model.id, category.id), []).append(item)
            item_cache[key] = item
            return item

        async def resolve_line(sheet_cat, model_str, overrides):
            real_cat_name = CATEGORY_MAP.get(sheet_cat, sheet_cat)
            category = categories[real_cat_name]
            override_key = (real_cat_name, model_str)
            variant_override = VARIANT_OVERRIDES.get(override_key)

            if override_key in overrides:
                resolved = [(b, m, None) for b, m in overrides[override_key]]
            else:
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
                resolved = []
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
                        if len(its) == 1:
                            # Only one real item for this model in this category -- no
                            # ambiguity to resolve, reuse it exactly as-is (its variant
                            # might be a real distinguishing value like "5G", not blank;
                            # defaulting to variant=None here would wrongly create a
                            # second, duplicate item).
                            variant = its[0].variant
                        elif len(its) > 1:
                            if variant_override:
                                variant = variant_override
                            else:
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
                                        f"{model_str!r} cat={real_cat_name!r}: model {model_row.name!r} "
                                        f"has items {[(i.id, i.variant) for i in its]}, no color token to pick one"
                                    )
                        resolved.append((brand_name, model_row.name, variant))
                    elif len(hits) > 1:
                        raise ResolutionError(f"{model_str!r}: token {tok!r} ambiguous across {hits}")
                    else:
                        if len(brand_tokens) == 1:
                            resolved.append((brand_tokens[0], tok, None))
                        else:
                            raise ResolutionError(f"{model_str!r}: new model {tok!r}, ambiguous brand {brand_tokens}")

            primary_brand, primary_model_name, primary_variant = resolved[0]
            brand = await get_or_create_brand(primary_brand)
            model = await get_or_create_model(brand, primary_model_name)
            item = await get_or_create_item(category, model, brand, primary_variant)
            compat = []
            for cb, cm, cv in resolved[1:]:
                cbrand = await get_or_create_brand(cb)
                cmodel = await get_or_create_model(cbrand, cm)
                compat.append(cmodel)
            for cmodel in compat:
                existing = await db.scalar(
                    select(ItemCompatibleModel).where(
                        ItemCompatibleModel.item_id == item.id, ItemCompatibleModel.model_id == cmodel.id
                    )
                )
                if existing is None:
                    db.add(ItemCompatibleModel(item_id=item.id, model_id=cmodel.id))
            return item

        # ---- Build a unified, date-ordered transaction list ----
        # tx kind: "purchase" (local purchase line, maybe with an attached same-day resale)
        #          "sale_group" (one Credit Sale order: date+customer+invoice, multiple lines)
        transactions = []

        for row in lp_real:
            transactions.append({"kind": "purchase", "date": row["Ledger Date"], "row": row})

        def cs_group_key(r):
            return (r["Ledger Date"], r["Customer"], r["INVOICE#"])

        for key, group in itertools.groupby(cs_real, key=cs_group_key):
            date, customer, invoice = key
            transactions.append({
                "kind": "sale_group", "date": date, "customer": customer, "invoice": invoice,
                "rows": list(group),
            })

        # Local Purchase before Credit Sale on the same date (stock must exist before it's sold).
        transactions.sort(key=lambda t: (t["date"], 0 if t["kind"] == "purchase" else 1))

        errors = []
        free_adjustments = []
        po_counter = 0
        so_counter = 0

        print(f"Total transactions to process in order: {len(transactions)}")

        if not apply:
            # Resolution-only dry run, PLUS a full in-memory simulation of the stock flow
            # (seeded from real current StockLot quantities) so an InsufficientStock failure
            # partway through the real --apply run -- which costs a manual cleanup, as
            # happened once already this session -- gets caught here instead.
            virtual_stock: dict[int, Decimal] = {}

            async def virtual_available(item_id: int) -> Decimal:
                if item_id not in virtual_stock:
                    total = await db.scalar(
                        select(func.coalesce(func.sum(StockLot.qty_remaining), 0))
                        .where(StockLot.item_id == item_id)
                    )
                    virtual_stock[item_id] = total or Decimal(0)
                return virtual_stock[item_id]

            insufficient_preview = []
            for tx in transactions:
                try:
                    if tx["kind"] == "purchase":
                        row = tx["row"]
                        item = await resolve_line(row["Category"], row["Model"], LOCAL_PURCHASE_OVERRIDES)
                        qty = Decimal(str(row["Qty"]))
                        await virtual_available(item.id)
                        virtual_stock[item.id] += qty
                        if row["Sold To (Party)"] and str(row["Invoice #"]) not in cs_invoice_numbers:
                            await resolve_party(row["Sold To (Party)"])
                            avail = await virtual_available(item.id)
                            if avail < qty:
                                raise ResolutionError(f"Sold-To resale needs {qty}, only {avail} available")
                            virtual_stock[item.id] -= qty
                        await resolve_party(row["Supplier"])
                    else:
                        await resolve_party(tx["customer"])
                        for row in tx["rows"]:
                            item = await resolve_line(row["Category"], row["Model"], MANUAL_OVERRIDES)
                            if row["Rate"] == 0:
                                continue  # free/sample -- handled as a separate stock adjustment, same as --apply
                            qty = Decimal(str(row["Qty"]))
                            avail = await virtual_available(item.id)
                            if avail < qty:
                                # Per the user's decision: logged ledger-only in --apply, not an error here.
                                insufficient_preview.append(
                                    (row["_row"], f"needs {qty} of item {item.id} ({item.sku}), only {avail} available")
                                )
                                continue
                            virtual_stock[item.id] -= qty
                except ResolutionError as e:
                    label = tx.get("row", {}).get("_row") if tx["kind"] == "purchase" else tx.get("invoice")
                    errors.append((label, str(e)))
            print(f"Resolution errors: {len(errors)}")
            for e in errors[:40]:
                print("  ERROR:", e)
            print(f"\nInsufficient-stock lines (will be logged ledger-only, no stock effect, per your decision): "
                  f"{len(insufficient_preview)}")
            for p in insufficient_preview[:40]:
                print("  ", p)
            # Exception row preview
            print(f"\nLocal Purchase exception row 21 (A.Power Traders): "
                  f"Rs {lp_exception['Qty'] * lp_exception['Rate']} payable, no stock effect, "
                  f"resold to {lp_exception['Sold To (Party)']!r} with no recorded sale amount")
            await db.rollback()
            print("\n[DRY RUN] Nothing written. Re-run with --apply to commit.")
            return

        if errors:
            raise ResolutionError(f"{len(errors)} unresolved rows -- aborting, nothing written")

        # ---- Apply for real, one transaction at a time, in order ----
        # Same virtual-stock tracking as the dry-run simulation -- lines that would need
        # more than what's actually available (confirmed this session: ~26 models with no
        # purchasing history behind them at all) go to the ledger-only exception path
        # instead of a real SalesOrderLine, per the user's explicit decision to apply this
        # now and investigate the root cause separately later.
        apply_virtual_stock: dict[int, Decimal] = {}

        async def apply_virtual_available(item_id: int) -> Decimal:
            if item_id not in apply_virtual_stock:
                total = await db.scalar(
                    select(func.coalesce(func.sum(StockLot.qty_remaining), 0)).where(StockLot.item_id == item_id)
                )
                apply_virtual_stock[item_id] = total or Decimal(0)
            return apply_virtual_stock[item_id]

        insufficient_stock_count = 0
        resumed_count = 0
        for tx in transactions:
            if tx["kind"] == "purchase":
                row = tx["row"]
                supplier = await resolve_party(row["Supplier"])
                item = await resolve_line(row["Category"], row["Model"], LOCAL_PURCHASE_OVERRIDES)
                qty_check = Decimal(str(row["Qty"]))
                # Resumable: if a previous --apply run already got through this exact row
                # (same supplier/date/invoice/item/qty -- an invoice can have more than one
                # line, so invoice# alone isn't a unique key) before failing on a later one,
                # skip it rather than creating a duplicate purchase order.
                already = await db.scalar(
                    select(PurchaseOrderLine).join(PurchaseOrder).where(
                        PurchaseOrder.party_id == supplier.id, PurchaseOrder.order_date == row["Ledger Date"],
                        PurchaseOrder.invoice_number == (str(row["Invoice #"]) if row["Invoice #"] is not None else None),
                        PurchaseOrder.source == "local",
                        PurchaseOrderLine.item_id == item.id, PurchaseOrderLine.qty == qty_check,
                    )
                )
                if already is not None:
                    resumed_count += 1
                    continue
                rate_pkr = Decimal(str(row["Rate"]))
                qty = Decimal(str(row["Qty"]))

                po = PurchaseOrder(
                    party_id=supplier.id, order_date=row["Ledger Date"], source="local",
                    status="allocated", invoice_number=str(row["Invoice #"]) if row["Invoice #"] is not None else None,
                )
                db.add(po)
                await db.flush()
                po_line = PurchaseOrderLine(
                    purchase_order_id=po.id, item_id=item.id, qty=qty, rate_rmb=None,
                    rate_pkr=rate_pkr, landed_cost_pkr=rate_pkr,
                )
                db.add(po_line)
                await db.flush()
                await ledger_service.post_entry(
                    db, entry_date=row["Ledger Date"], account="Accounts Payable", credit=qty * rate_pkr,
                    reference_type="purchase_order", reference_id=po.id, party_id=supplier.id,
                )
                lot = StockLot(
                    purchase_order_line_id=po_line.id, item_id=item.id, qty_received=qty,
                    qty_remaining=qty, landed_cost_pkr=rate_pkr, received_date=row["Ledger Date"],
                )
                db.add(lot)
                await db.flush()
                db.add(StockMovement(
                    stock_lot_id=lot.id, movement_type="receipt", qty_delta=qty,
                    reason=None, movement_date=row["Ledger Date"],
                ))
                po.status = "received"
                po_counter += 1
                await apply_virtual_available(item.id)
                apply_virtual_stock[item.id] += qty

                if row["Sold To (Party)"] and str(row["Invoice #"]) not in cs_invoice_numbers:
                    buyer = await resolve_party(row["Sold To (Party)"])
                    so = SalesOrder(party_id=buyer.id, order_date=row["Ledger Date"],
                                     invoice_number=str(row["Invoice #"]) if row["Invoice #"] is not None else None)
                    db.add(so)
                    await db.flush()
                    consumptions = await inventory_service.consume_stock_fifo(
                        db, item_id=item.id, qty_needed=qty, movement_date=row["Ledger Date"]
                    )
                    apply_virtual_stock[item.id] -= qty
                    line = SalesOrderLine(sales_order_id=so.id, item_id=item.id, qty=qty, rate_pkr=rate_pkr)
                    db.add(line)
                    await db.flush()
                    for c in consumptions:
                        db.add(SalesOrderLineLot(
                            sales_order_line_id=line.id, stock_lot_id=c.stock_lot_id,
                            qty_consumed=c.qty_consumed, unit_cost_pkr=c.unit_cost_pkr,
                        ))
                    await ledger_service.post_entry(
                        db, entry_date=row["Ledger Date"], account="Accounts Receivable", debit=qty * rate_pkr,
                        reference_type="sales_order", reference_id=so.id, party_id=buyer.id,
                    )
                    so_counter += 1
                await db.commit()
            else:
                party = await resolve_party(tx["customer"])
                # Zero-rate (free/sample) rows are collected regardless of whether this
                # group's main sale was already processed in an earlier --apply attempt --
                # they're logically independent of the SalesOrder/SalesLogException below,
                # and skipping the whole group would otherwise silently drop them on resume
                # (found and fixed this session: that's exactly what happened the first time).
                for row in tx["rows"]:
                    if row["Rate"] == 0:
                        item = await resolve_line(row["Category"], row["Model"], MANUAL_OVERRIDES)
                        free_adjustments.append({"row": row["_row"], "item": item, "qty": Decimal(str(row["Qty"])),
                                                  "date": row["Ledger Date"], "invoice": row["INVOICE#"]})
                # Resumable: a (party, date, invoice#) group produces a SalesOrder (if any
                # line had stock) and/or SalesLogException rows (if any line didn't) -- if
                # either already exists from a previous --apply run that got this far before
                # failing on a later transaction, skip the whole group rather than
                # re-creating/re-logging it.
                invoice_str = str(tx["invoice"]) if tx["invoice"] is not None else None
                already_so = await db.scalar(
                    select(SalesOrder).where(
                        SalesOrder.party_id == party.id, SalesOrder.order_date == tx["date"],
                        SalesOrder.invoice_number == invoice_str,
                    )
                )
                already_log = await db.scalar(
                    select(SalesLogException).where(
                        SalesLogException.party_id == party.id, SalesLogException.entry_date == tx["date"],
                        SalesLogException.invoice_number == invoice_str, SalesLogException.kind == "insufficient_stock",
                    )
                )
                if already_so is not None or already_log is not None:
                    resumed_count += 1
                    continue
                lines_data = []
                insufficient_lines = []
                for row in tx["rows"]:
                    if row["Rate"] == 0:
                        continue  # already collected into free_adjustments above
                    item = await resolve_line(row["Category"], row["Model"], MANUAL_OVERRIDES)
                    qty = Decimal(str(row["Qty"]))
                    avail = await apply_virtual_available(item.id)
                    if avail < qty:
                        insufficient_lines.append({
                            "row": row, "item": item, "qty": qty, "rate_pkr": Decimal(str(row["Rate"])),
                        })
                        insufficient_stock_count += 1
                        continue
                    apply_virtual_stock[item.id] -= qty
                    lines_data.append({"item": item, "qty": qty, "rate_pkr": Decimal(str(row["Rate"]))})

                if lines_data:
                    so = SalesOrder(party_id=party.id, order_date=tx["date"],
                                     invoice_number=str(tx["invoice"]) if tx["invoice"] is not None else None)
                    db.add(so)
                    await db.flush()
                    total_pkr = Decimal(0)
                    for l in lines_data:
                        # Defensive: my pre-check (apply_virtual_available) is a prediction,
                        # not a transaction-isolated guarantee -- if it's ever wrong for any
                        # reason, fail this one line into the same ledger-only exception path
                        # instead of crashing the whole run (root cause to investigate later).
                        try:
                            consumptions = await inventory_service.consume_stock_fifo(
                                db, item_id=l["item"].id, qty_needed=l["qty"], movement_date=tx["date"]
                            )
                        except InsufficientStock:
                            insufficient_lines.append({
                                "row": {"Category": None}, "item": l["item"], "qty": l["qty"], "rate_pkr": l["rate_pkr"],
                            })
                            insufficient_stock_count += 1
                            continue
                        line = SalesOrderLine(sales_order_id=so.id, item_id=l["item"].id, qty=l["qty"], rate_pkr=l["rate_pkr"])
                        db.add(line)
                        await db.flush()
                        for c in consumptions:
                            db.add(SalesOrderLineLot(
                                sales_order_line_id=line.id, stock_lot_id=c.stock_lot_id,
                                qty_consumed=c.qty_consumed, unit_cost_pkr=c.unit_cost_pkr,
                            ))
                        total_pkr += l["qty"] * l["rate_pkr"]
                    if total_pkr > 0:
                        await ledger_service.post_entry(
                            db, entry_date=tx["date"], account="Accounts Receivable", debit=total_pkr,
                            reference_type="sales_order", reference_id=so.id, party_id=party.id,
                        )
                        so_counter += 1
                    else:
                        await db.delete(so)

                # No real purchasing history behind these specific lines (confirmed this
                # session -- root cause to be investigated separately later). Post the
                # real money, skip the stock deduction, log for audit -- same pattern as
                # every other "can't honestly back this with real stock" case this session.
                for il in insufficient_lines:
                    log = SalesLogException(
                        entry_date=tx["date"], kind="insufficient_stock", category_name=il["row"]["Category"],
                        qty=il["qty"], rate_pkr=il["rate_pkr"], amount_pkr=il["qty"] * il["rate_pkr"],
                        party_id=party.id, invoice_number=str(tx["invoice"]) if tx["invoice"] is not None else None,
                        note=f"item {il['item'].id} ({il['item'].sku}) had no recorded stock to draw from",
                    )
                    db.add(log)
                    await db.flush()
                    entry = await ledger_service.post_entry(
                        db, entry_date=tx["date"], account="Accounts Receivable", debit=il["qty"] * il["rate_pkr"],
                        reference_type="sales_log_exception", reference_id=log.id, party_id=party.id,
                    )
                    await db.flush()
                    log.ledger_entry_id = entry.id
                await db.commit()

        for a in free_adjustments:
            # Resumable: same reason text is deterministic per sheet row, so re-running
            # after this already applied (e.g. a later --apply attempt) must not double-deduct.
            reason = f"Free/sample, zero-rate per day book (invoice #{a['invoice']})"
            already = await db.scalar(
                select(StockMovement).join(StockLot).where(
                    StockLot.item_id == a["item"].id, StockMovement.reason == reason,
                    StockMovement.movement_date == a["date"],
                )
            )
            if already is not None:
                resumed_count += 1
                continue
            lots = (await db.scalars(
                select(StockLot).where(StockLot.item_id == a["item"].id, StockLot.qty_remaining > 0)
                .order_by(StockLot.received_date, StockLot.id)
            )).all()
            remaining = a["qty"]
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
            if remaining > 0:
                # Same "no purchasing history behind this item" pattern as the 231
                # insufficient_stock lines -- nothing to mark damaged against, so just
                # note it (no stock_movement for the unfulfilled part) rather than fail
                # the whole run.
                print(f"  NOTE: row {a['row']} free/sample adjustment only had stock for "
                      f"{a['qty'] - remaining} of {a['qty']} (item {a['item'].id}, {a['item'].sku}) -- "
                      f"rest has no purchasing history to mark damaged against")
            await db.commit()

        # Local Purchase exception row 21: Accounts Payable only, no stock, no matching sale.
        a_power = await resolve_party(lp_exception["Supplier"])
        already_exc = await db.scalar(
            select(LedgerEntry).where(
                LedgerEntry.reference_type == "local_purchase_exception",
                LedgerEntry.reference_id == lp_exception["_row"],
            )
        )
        if already_exc is None:
            amount = Decimal(str(lp_exception["Qty"])) * Decimal(str(lp_exception["Rate"]))
            await ledger_service.post_entry(
                db, entry_date=lp_exception["Ledger Date"], account="Accounts Payable", credit=amount,
                reference_type="local_purchase_exception", reference_id=lp_exception["_row"], party_id=a_power.id,
            )
            await db.commit()
        else:
            resumed_count += 1

        print(f"\nDone. {po_counter} purchase orders, {so_counter} sales orders, "
              f"{len(free_adjustments)} free/sample adjustments found ({resumed_count} skipped as already-resumed), "
              f"{insufficient_stock_count} insufficient-stock lines logged ledger-only applied.")


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
