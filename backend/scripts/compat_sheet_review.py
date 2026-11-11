"""Compare the owner's "COMPATIBLE MODELS SYSTEM" workbook with the catalog (READ-ONLY) and write a review.

Each row of the workbook's "Database" sheet is: Category, Main_Model (the product that is actually sold), and
Compatible_Models (every phone that product fits, including the main one, across brands). In the app that is one
Item (category + primary model) with the other phones as `item_compatible_model` rows.

Writes COMPATIBLE_MODELS_REVIEW.md (repo root) and compat_review/*.csv. Nothing in the database is changed.

    PROD_DSN=postgresql://... python backend/scripts/compat_sheet_review.py [--workbook "/path/COMPATIBLE MODELS SYSTEM (1).xlsx"]
"""
import argparse
import asyncio
import collections
import csv
import os
import re
import sys
import warnings
from pathlib import Path

import asyncpg
import openpyxl

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.catalog.naming import match_key, parse_sheet_phone  # noqa: E402

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent.parent
OUT_MD = ROOT / "COMPATIBLE_MODELS_REVIEW.md"
OUT_DIR = ROOT / "compat_review"
DEFAULT_WORKBOOK = "/home/m-taha/Desktop/upwork/ayan/COMPATIBLE MODELS SYSTEM (1).xlsx"

# Workbook category -> catalog category name.
CATEGORY_MAP = {"OG": "OG Glass Protector", "DUSTPLUG": "Dust Plug", "TPU": "TPU Case", "ITSME-PRIVACY": "Its Me Privacy Protector"}
NEW_BRANDS = {"Motorola", "LG", "Honor"}  # not in the catalog today (Redmi is renamed Xiaomi by the cleanup)


def parse_token(token: str):
    """'SAM-A324G' -> (catalog brand, standard name, review reason or '') using the shared reader in naming.py."""
    phone = parse_sheet_phone(token)
    return phone.brand, phone.name, "; ".join(phone.reasons)


def write_csv(name, header, rows):
    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / name, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)


async def main(workbook):
    wb = openpyxl.load_workbook(workbook, data_only=True)
    sheet_rows = [(r[0], str(r[1]).strip(), str(r[2] or "").strip()) for r in wb["Database"].iter_rows(min_row=2, values_only=True) if r[0] and r[1]]

    conn = await asyncpg.connect(os.environ["PROD_DSN"].split("?")[0], ssl=True, timeout=30)
    try:
        await conn.execute("set default_transaction_read_only = on")
        models = await conn.fetch("select m.id, m.name, m.is_active, b.name brand from model m join brand b on b.id=m.brand_id")
        items = await conn.fetch("select i.id, i.sku, i.variant, i.model_id, cat.name category, "
                                 "(select coalesce(sum(sl.qty_remaining),0) from stock_lot sl where sl.item_id=i.id) stock "
                                 "from item i join category cat on cat.id=i.category_id where i.is_active")
        compat = collections.defaultdict(set)
        for r in await conn.fetch("select item_id, model_id from item_compatible_model"):
            compat[r["item_id"]].add(r["model_id"])
    finally:
        await conn.close()

    by_id = {m["id"]: m for m in models}
    key_to_models = collections.defaultdict(list)
    for m in models:
        key_to_models[(m["brand"], match_key(m["brand"], m["name"]))].append(m)

    # ---- every distinct phone named in the sheet
    tokens = {}
    for cat, main, comp in sheet_rows:
        for t in [main] + [x.strip() for x in comp.split(",") if x.strip()]:
            if t not in tokens:
                brand, name, why = parse_token(t)
                tokens[t] = dict(brand=brand, name=name, why=why, key=match_key(brand, name) if brand and name else "")
    tok_rows, existing, new, flagged = [], 0, 0, 0
    distinct = {}
    for t, d in sorted(tokens.items()):
        if d["why"]:
            status = "REVIEW"; flagged += 1
        else:
            found = key_to_models.get((d["brand"], d["key"]))
            status = "EXISTS" if found else "NEW"
            existing += status == "EXISTS"
            new += status == "NEW"
            distinct[(d["brand"], d["key"])] = d["name"]
        tok_rows.append([t, d["brand"] or "", d["name"], status, d["why"]])
    write_csv("phones.csv", ["sheet_text", "brand", "standard_name", "status", "why_review"], tok_rows)
    new_brand_models = sorted({(d["brand"], d["name"]) for d in tokens.values() if d["brand"] in NEW_BRANDS and not d["why"]})

    # ---- rows: does the item exist, and which compatible links would be added
    items_by_key = collections.defaultdict(list)
    for it in items:
        m = by_id[it["model_id"]]
        items_by_key[(it["category"], m["brand"], match_key(m["brand"], m["name"]))].append(it)
    row_out, n_item, n_noitem, n_unmapped, add_links, have_links, overlap = [], 0, 0, 0, 0, 0, 0
    for cat, main, comp in sheet_rows:
        category = CATEGORY_MAP.get(cat)
        brand, name, why = parse_token(main)
        comp_tokens = [x.strip() for x in comp.split(",") if x.strip()]
        if not category or why or not brand:
            n_unmapped += 1
            row_out.append([cat, main, comp, "", "", "REVIEW", why or "category not mapped", 0, 0])
            continue
        found = items_by_key.get((category, brand, match_key(brand, name)), [])
        if not found:
            n_noitem += 1
            row_out.append([cat, main, comp, "", name, "NO ITEM YET", "", len(comp_tokens), 0])
            continue
        n_item += 1
        it = max(found, key=lambda x: x["stock"])
        have = {match_key(by_id[c]["brand"], by_id[c]["name"]) for c in compat[it["id"]]} | {match_key(by_id[it["model_id"]]["brand"], by_id[it["model_id"]]["name"])}
        to_add = []
        for t in comp_tokens:
            b, nm, w = parse_token(t)
            if w or not b:
                continue
            k = match_key(b, nm)
            if k in have:
                have_links += 1
            else:
                to_add.append(f"{b} {nm}"); add_links += 1
        row_out.append([cat, main, comp, it["sku"], name, "ITEM EXISTS", "", len(comp_tokens), len(to_add)])
    write_csv("rows.csv", ["sheet_category", "main_model", "compatible_models", "existing_item_sku", "standard_main", "status", "note", "phones_in_group", "links_to_add"], row_out)

    # ---- catalog items with stock that the sheet does not cover
    sheet_keys = {(CATEGORY_MAP.get(c), *(lambda b_n: (b_n[0], match_key(b_n[0], b_n[1])))(parse_token(m)[:2])) for c, m, _ in sheet_rows if CATEGORY_MAP.get(c) and parse_token(m)[0]}
    covered_cats = set(CATEGORY_MAP.values())
    uncovered = [it for it in items if it["category"] in covered_cats and it["stock"] > 0 and (it["category"], by_id[it["model_id"]]["brand"], match_key(by_id[it["model_id"]]["brand"], by_id[it["model_id"]]["name"])) not in sheet_keys]
    write_csv("stock_items_not_in_sheet.csv", ["sku", "category", "stock"], [[it["sku"], it["category"], it["stock"]] for it in uncovered])

    cat_counts = collections.Counter(r[0] for r in sheet_rows)
    lines = [
        "# Compatible models review (from `COMPATIBLE MODELS SYSTEM (1).xlsx`)", "",
        "Generated read-only. **Nothing has been changed.**", "",
        "## What the sheet says", "",
        f"- {len(sheet_rows)} products in 4 categories: " + ", ".join(f"{k} {v}" for k, v in cat_counts.items()) + ". Each row is the product that is sold (Main_Model) and every phone it fits (Compatible_Models, across brands).",
        f"- {len(tokens)} distinct phones are named. {existing} already exist in the catalog, {new} are new, {flagged} need your decision (unclear text).",
        f"- Products: {n_item} already exist as items in the catalog, {n_noitem} do not exist as items yet, {n_unmapped} rows are unclear.",
        f"- Links: {add_links} new \"fits\" links would be added to existing items; {have_links} are already there.",
        f"- New brands needed: Motorola, LG and Honor ({len(new_brand_models)} phones); the existing brand Redmi is renamed Xiaomi.", "",
        "## Decisions for you", "",
        f"1. **Create the {new} new phones** (as models, so they can be linked)? They would be created with the standard name.",
        f"2. **The {n_noitem} products that are not items yet:** create them as items (no stock) so the fitment is recorded, or only link fitments to items that already exist ({n_item}).",
        "3. **New brands Motorola, LG and Honor (decided):** they are created.",
        "4. **Brand groups (decided):** Redmi / Mi / Poco / Xiaomi / HM / XM go under the brand \"Xiaomi\" (the line name stays in the model: Redmi 13C, Poco M6 Pro); Honor is its own brand; RME and REALME go under \"Realme\".",
        f"5. **{flagged} phones with unclear text** (list below) - tell me the right name, or skip them.", "",
        "Full lists: `compat_review/phones.csv`, `rows.csv`, `stock_items_not_in_sheet.csv`.", "",
        "## Phones needing a decision", "", "| Sheet text | Why |", "|---|---|",
    ]
    for r in [x for x in tok_rows if x[3] == "REVIEW"][:80]:
        lines.append(f"| `{r[0]}` | {r[4]} |")
    if flagged > 80:
        lines.append(f"| ... {flagged - 80} more in phones.csv | |")
    lines += ["", f"## Catalog items with stock that the sheet does not cover: {len(uncovered)}", "", "(see `stock_items_not_in_sheet.csv`; the sheet only covers OG, Dust Plug, TPU and Its Me Privacy)"]
    OUT_MD.write_text("\n".join(lines) + "\n")
    print(f"rows {len(sheet_rows)} | phones {len(tokens)}: exists {existing}, new {new}, review {flagged} | items exist {n_item}, no item {n_noitem}, unclear {n_unmapped} | links to add {add_links}, already {have_links} | stock items not in sheet {len(uncovered)} | Motorola/LG phones {len(new_brand_models)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workbook", default=DEFAULT_WORKBOOK)
    asyncio.run(main(parser.parse_args().workbook))
