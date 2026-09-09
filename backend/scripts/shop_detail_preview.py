"""Phase 1 (read-only): parse Shop Detail.xlsx into a reviewable mapping.

Writes a CSV to the scratchpad dir and prints a summary. Makes NO database
writes. Run with the scratch venv that has openpyxl:
    <scratch>/xlsx-venv/bin/python shop_detail_preview.py [--db]

Pass --db to cross-check ambiguous brand tokens (bare "A54", "Note 60", ...)
against Brand/Model rows already in the production DB via asyncpg -- without
it, ambiguous tokens are just reported unresolved.
"""

import csv
import os
import sys

import openpyxl

sys.path.insert(0, os.path.dirname(__file__))
from shop_detail_data import (
    BRAND_COLUMN_SHEETS,
    BRAND_HEADER_ALIASES,
    CATEGORY_AVG_RATE,
    EXCLUDED_TOKENS,
    IPHONE_DEFAULT_SHEETS,
    JUN_BEST_LENZ_RATES,
    SHEET_TO_CATEGORY,
    SKIP_PRODUCT_EXACT,
    SKIP_PRODUCT_PREFIXES,
    SKIP_PRODUCT_SUFFIXES,
    TOKEN_OVERRIDES,
    XLSX_PATH,
)
from shop_detail_resolve import (
    build_catalog_index,
    normalize_iphone_model,
    resolve_token,
)

OUT_CSV = os.environ.get("SHOP_DETAIL_OUT_CSV", "/tmp/shop_detail_preview.csv")
CATALOG_JSON = os.environ.get("SHOP_DETAIL_CATALOG_JSON")

PROD_DSN = (
    "postgresql://neondb_owner:npg_EB7tMT1PWRfb@"
    "ep-hidden-fog-azzrinlv.c-3.ap-southeast-1.aws.neon.tech/neondb"
)


def should_skip_row(first_cell) -> bool:
    if first_cell is None:
        return True
    s = str(first_cell).strip()
    if s in SKIP_PRODUCT_EXACT:
        return True
    if any(s.upper().startswith(p) for p in SKIP_PRODUCT_PREFIXES):
        return True
    if any(s.upper().endswith(suf) for suf in SKIP_PRODUCT_SUFFIXES):
        return True
    return False


def to_qty(value) -> float:
    if value is None:
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


def rate_for(category: str, product_label: str) -> float:
    if category == "Jun Best Lens Protector":
        return JUN_BEST_LENZ_RATES.get(product_label, CATEGORY_AVG_RATE[category])
    return CATEGORY_AVG_RATE[category]


def resolve_cell(model_cell: str, catalog_index: dict | None = None, sheet_name: str | None = None) -> list[dict]:
    """Split on '/' and resolve each token; a token with no matched brand
    inherits the brand of the first token in the group that DID match."""
    tokens = [t.strip() for t in str(model_cell).split("/") if t.strip()]
    resolved = []
    group_brand = None
    for tok in tokens:
        if tok in EXCLUDED_TOKENS:
            resolved.append(
                {"raw_token": tok, "brand": None, "model": tok, "variant": None,
                 "note": "excluded -- no known phone model matches this (see EXCLUDED_TOKENS)"}
            )
            continue
        if tok in TOKEN_OVERRIDES:
            brand, model = TOKEN_OVERRIDES[tok]
            group_brand = group_brand or brand
            resolved.append({"raw_token": tok, "brand": brand, "model": model, "variant": None, "note": "hand-resolved override"})
            continue

        res = resolve_token(tok, catalog_index)
        brand = res.brand or group_brand
        model = res.model
        if brand is None and res.note.startswith("ambiguous") and sheet_name in IPHONE_DEFAULT_SHEETS:
            brand = "iPhone"
            model = normalize_iphone_model(res.model)
            note = f"{res.note} -- defaulted to iPhone (sheet default)"
        elif not res.brand and brand:
            # inherited the group's brand -- res.model is still raw/unnormalized text
            model = normalize_iphone_model(res.model) if brand == "iPhone" else res.model
            note = "inherited brand from group"
        else:
            note = res.note if not brand else ""
        if res.brand and group_brand is None:
            group_brand = res.brand
        resolved.append(
            {
                "raw_token": tok,
                "brand": brand,
                "model": model,
                "variant": res.variant,
                "note": note,
            }
        )
    return resolved


def main():
    wb = openpyxl.load_workbook(XLSX_PATH, data_only=True)
    catalog_index = None
    if CATALOG_JSON:
        import json
        with open(CATALOG_JSON) as f:
            catalog_index = build_catalog_index(json.load(f))
        print(f"Loaded catalog cross-reference: {len(catalog_index)} canonical model keys\n")
    rows_out = []
    unresolved_summary: dict[str, list[str]] = {}

    for sheet_name, category in SHEET_TO_CATEGORY.items():
        ws = wb[sheet_name]
        is_brand_col = sheet_name in BRAND_COLUMN_SHEETS

        header = [str(c).strip().upper() if c else "" for c in next(ws.iter_rows(min_row=1, max_row=1, values_only=True))]
        received_idx = next(i for i, h in enumerate(header) if h.startswith("RECEIVED"))
        model_idx = 1  # MODEL is always column B across every sheet/layout

        current_brand = None  # for BRAND_COLUMN_SHEETS: sticky brand from a section header row
        row_id = 0  # stable per-original-row id -- distinguishes rows that share identical (model_cell, qty)

        for row in ws.iter_rows(min_row=2, values_only=True):
            first = row[0]
            if should_skip_row(first):
                continue

            if is_brand_col:
                brand_raw = str(first).strip()
                # strip batch/annotation suffixes like " (BATCH 1)", " (BATCH 2 - DUST PLUG)"
                brand_key = brand_raw.split("(")[0].strip().upper()
                brand_clean = BRAND_HEADER_ALIASES.get(brand_key, brand_key.title())
                model_cell = row[model_idx]
                received = to_qty(row[received_idx] if len(row) > received_idx else None)
                if model_cell is None:
                    current_brand = brand_clean  # section header row, e.g. ('IPHONE', None, None)
                    continue
                product_label = category
            else:
                product_label = str(first).strip()
                model_cell = row[model_idx]
                received = to_qty(row[received_idx] if len(row) > received_idx else None)

            if model_cell is None or received <= 0:
                continue
            row_id += 1

            for resolved in resolve_cell(model_cell, catalog_index, sheet_name):
                brand = resolved["brand"]
                model = resolved["model"]
                if is_brand_col and not brand and current_brand:
                    brand = current_brand
                    model = normalize_iphone_model(model) if brand == "iPhone" else model
                rate = rate_for(category, product_label)
                out_row = {
                    "row_id": f"{sheet_name}#{row_id}",
                    "sheet": sheet_name,
                    "category": category,
                    "product_label": product_label,
                    "raw_model_cell": model_cell,
                    "raw_token": resolved["raw_token"],
                    "brand": brand or "",
                    "model": model,
                    "variant": resolved["variant"] or "",
                    "received_qty": received,
                    "rate_pkr": rate,
                    "unresolved": "" if brand else "UNRESOLVED",
                    "note": resolved["note"],
                }
                rows_out.append(out_row)
                if not brand:
                    unresolved_summary.setdefault(sheet_name, []).append(
                        f"{resolved['raw_token']!r} (from cell {model_cell!r}, qty={received})"
                    )

    with open(OUT_CSV, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "row_id", "sheet", "category", "product_label", "raw_model_cell", "raw_token",
                "brand", "model", "variant", "received_qty", "rate_pkr", "unresolved", "note",
            ],
        )
        writer.writeheader()
        writer.writerows(rows_out)

    total_qty = sum(r["received_qty"] for r in rows_out)
    unresolved_qty = sum(r["received_qty"] for r in rows_out if r["unresolved"])
    print(f"Wrote {len(rows_out)} resolved-token rows to {OUT_CSV}")
    print(f"Total received qty across all rows: {total_qty:.0f}")
    print(f"Unresolved rows: {sum(len(v) for v in unresolved_summary.values())} "
          f"(qty {unresolved_qty:.0f}, {100*unresolved_qty/total_qty:.1f}% of total)\n")

    for sheet, items in unresolved_summary.items():
        print(f"--- {sheet} ({len(items)} unresolved) ---")
        for item in items:
            print(f"  {item}")
        print()


if __name__ == "__main__":
    main()
