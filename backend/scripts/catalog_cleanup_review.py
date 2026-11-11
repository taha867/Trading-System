"""Build the catalog cleanup review (READ-ONLY): what would be merged, renamed and re-coded, and what needs a human.

Reads production through a read-only transaction, applies the naming standard in src/catalog/naming.py, and writes
  CATALOG_CLEANUP_REVIEW.md                       (repo root: the summary and the items that need your decision)
  catalog_cleanup_review/models.csv  items.csv  fitment.csv  skus.csv   (the full lists)
Nothing in the database is changed. Review the files, correct anything wrong, and only then is the cleanup script run.

    PROD_DSN=postgresql://... python backend/scripts/catalog_cleanup_review.py [--workbook "/path/Daily Cash Book (Sept 2026).xlsx"]
"""
import argparse
import asyncio
import collections
import csv
import os
import sys
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.catalog.naming import (  # noqa: E402
    BRAND_CODES, CATEGORY_CODES, build_sku, canonical_model_name, is_standard_sku, match_key, parse_fitment,
)

ROOT = Path(__file__).resolve().parent.parent.parent
OUT_MD = ROOT / "CATALOG_CLEANUP_REVIEW.md"
OUT_DIR = ROOT / "catalog_cleanup_review"
DEFAULT_WORKBOOK = "/home/m-taha/Desktop/upwork/shakeel accesories/Daily Cash Book/Daily Cash Book (Sept 2026).xlsx"


def write_csv(name, header, rows):
    OUT_DIR.mkdir(exist_ok=True)
    with open(OUT_DIR / name, "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(header)
        writer.writerows(rows)


async def load(conn):
    models = await conn.fetch(
        "select m.id, m.name, m.is_active, b.name brand, "
        "(select count(*) from item i where i.model_id=m.id and i.is_active) items, "
        "(select count(*) from item_compatible_model x where x.model_id=m.id) compat_refs "
        "from model m join brand b on b.id=m.brand_id order by b.name, m.name")
    items = await conn.fetch(
        "select i.id, i.sku, i.variant, i.model_id, i.category_id, cat.name category, "
        "(select count(*) from stock_lot sl where sl.item_id=i.id) lots, "
        "(select coalesce(sum(sl.qty_remaining),0) from stock_lot sl where sl.item_id=i.id) stock, "
        "(select count(*) from purchase_order_line l where l.item_id=i.id) pol, "
        "(select count(*) from sales_order_line l where l.item_id=i.id) sol "
        "from item i join category cat on cat.id=i.category_id where i.is_active")
    compat = collections.defaultdict(set)
    for r in await conn.fetch("select item_id, model_id from item_compatible_model"):
        compat[r["item_id"]].add(r["model_id"])
    return models, items, compat


def plan_models(models):
    """-> per model: (survivor id, canonical name, status, reasons)."""
    plans, groups = {}, collections.defaultdict(list)
    for m in models:
        result = canonical_model_name(m["brand"], m["name"])
        if result.needs_review or not result.name:
            plans[m["id"]] = dict(survivor=m["id"], canonical=result.name or m["name"], status="REVIEW", reasons="; ".join(result.reasons))
            continue
        groups[(m["brand"], match_key(m["brand"], m["name"]))].append((m, result.name))
    for (_, _), members in groups.items():
        active = [x for x in members if x[0]["is_active"]] or members
        # survivor: the most used model, then one already written in the standard, then the lowest id
        survivor = max(active, key=lambda x: (x[0]["items"] + x[0]["compat_refs"], x[0]["name"] == x[1], -x[0]["id"]))[0]
        canonical = members[0][1]
        for m, name in members:
            if m["id"] == survivor["id"]:
                status = "OK" if m["name"] == canonical and m["is_active"] else "RENAME"
            else:
                status = "MERGE"
            plans[m["id"]] = dict(survivor=survivor["id"], canonical=canonical, status=status, reasons="")
    return plans


def plan_items(items, compat, model_plan):
    groups = collections.defaultdict(list)
    for it in items:
        surv = model_plan[it["model_id"]]["survivor"]
        groups[(it["category_id"], surv, (it["variant"] or "").strip().upper())].append(it)
    item_plan = {}
    for key, members in groups.items():
        survivor = max(members, key=lambda x: (x["lots"] + x["pol"] + x["sol"], x["stock"], -x["id"]))
        for it in members:
            item_plan[it["id"]] = dict(survivor=survivor["id"], status="KEEP" if it["id"] == survivor["id"] else "MERGE")
    return groups, item_plan


def read_sheet_fitment(workbook):
    try:
        import openpyxl
    except ImportError:
        return []
    if not Path(workbook).exists():
        return []
    wb = openpyxl.load_workbook(workbook, data_only=True)
    texts = collections.Counter()
    ws = wb["Credit Sale"]
    headers = [ws.cell(1, c).value for c in range(1, ws.max_column + 1)]
    col = headers.index("Model") + 1
    for r in range(2, ws.max_row + 1):
        v = ws.cell(r, col).value
        if v and str(v).count("/") >= 2:
            texts[str(v).strip()] += 1
    return texts.most_common()


async def main(workbook):
    conn = await asyncpg.connect(os.environ["PROD_DSN"].split("?")[0], ssl=True, timeout=30)
    try:
        await conn.execute("set default_transaction_read_only = on")
        models, items, compat = await load(conn)
    finally:
        await conn.close()

    by_id = {m["id"]: m for m in models}
    model_plan = plan_models(models)
    groups, item_plan = plan_items(items, compat, model_plan)

    # ---- models.csv
    rows = []
    for m in models:
        p = model_plan[m["id"]]
        rows.append([m["brand"], m["id"], m["name"], "active" if m["is_active"] else "inactive", m["items"], p["status"], p["canonical"], by_id[p["survivor"]]["id"], p["reasons"]])
    write_csv("models.csv", ["brand", "model_id", "current_name", "state", "active_items", "action", "standard_name", "survivor_model_id", "why_review"], rows)
    n_ok = sum(1 for p in model_plan.values() if p["status"] == "OK")
    n_rename = sum(1 for p in model_plan.values() if p["status"] == "RENAME")
    n_merge = sum(1 for p in model_plan.values() if p["status"] == "MERGE")
    n_review = sum(1 for p in model_plan.values() if p["status"] == "REVIEW")

    # ---- items.csv + skus.csv
    survivors_final = {}
    sku_rows, item_rows, taken = [], [], set()
    keep = [it for it in items if item_plan[it["id"]]["status"] == "KEEP"]
    for it in sorted(keep, key=lambda x: x["id"]):
        mp = model_plan[it["model_id"]]
        surv_model = by_id[mp["survivor"]]
        base = None
        try:
            base = build_sku(it["category"], surv_model["brand"], mp["canonical"], it["variant"])
        except KeyError:
            base = None
        new_sku = base
        n = 2
        while new_sku and new_sku in taken:
            new_sku = f"{base}-{n}"
            n += 1
        if new_sku:
            taken.add(new_sku)
        sku_rows.append([it["id"], it["sku"], new_sku or "", it["category"], surv_model["brand"], mp["canonical"], it["variant"] or "", "REVIEW (model needs review)" if mp["status"] == "REVIEW" else ("same" if new_sku == it["sku"] else "change")])
    for it in sorted(items, key=lambda x: x["id"]):
        ip = item_plan[it["id"]]
        item_rows.append([it["category"], it["id"], it["sku"], ip["status"], ip["survivor"], it["lots"], it["stock"], it["pol"], it["sol"]])
    write_csv("skus.csv", ["item_id", "old_sku", "new_sku", "category", "brand", "model", "variant", "change"], sku_rows)
    write_csv("items.csv", ["category", "item_id", "sku", "action", "survivor_item_id", "stock_lots", "stock_remaining", "purchase_lines", "sales_lines"], item_rows)
    n_item_merge = sum(1 for p in item_plan.values() if p["status"] == "MERGE")
    n_sku_change = sum(1 for r in sku_rows if r[7] == "change")
    n_sku_review = sum(1 for r in sku_rows if r[7].startswith("REVIEW"))
    n_sku_std_before = sum(1 for it in items if is_standard_sku(it["sku"]))

    # ---- fitment.csv (compatible-model lists that disagree, and slash groups from the sheet)
    fit_rows = []
    cat_brand_key = collections.defaultdict(list)
    for it in items:
        mp = model_plan[it["model_id"]]
        cat_brand_key[(it["category"], by_id[mp["survivor"]]["brand"], mp["survivor"])].append(it)
    # items that hold the same compatible model in one category (fitment overlap) but are separate items
    overlap = collections.defaultdict(set)
    for it in items:
        if item_plan[it["id"]]["status"] != "KEEP":
            continue
        mids = {model_plan[it["model_id"]]["survivor"]} | {model_plan[m]["survivor"] for m in compat[it["id"]]}
        for mid in mids:
            # colours/finishes are separate items on purpose: only compare items with the same variant
            overlap[(it["category"], by_id[mid]["brand"], mid, (it["variant"] or "").strip().upper())].add(it["id"])
    item_by_id = {it["id"]: it for it in items}
    shared = {k: v for k, v in overlap.items() if len(v) > 1}
    for (category, brand, mid, _variant), ids in sorted(shared.items(), key=lambda kv: (kv[0][0], kv[0][1], by_id[kv[0][2]]["name"])):
        fit_rows.append(["items share a model", category, brand, model_plan[mid]["canonical"], " | ".join(f"{item_by_id[i]['sku']} (stock {item_by_id[i]['stock']})" for i in sorted(ids)), "decide: one item or two"])
    model_by_key = collections.defaultdict(list)
    for m in models:
        if m["is_active"] and model_plan[m["id"]]["status"] != "REVIEW":
            model_by_key[(m["brand"], match_key(m["brand"], m["name"]))].append(m)
    brand_words = {w for ws in __import__("src.catalog.naming", fromlist=["BRAND_PREFIXES"]).BRAND_PREFIXES.values() for w in ws} | {"PROT", "DPLUG", "DUST", "TPU", "OG"}
    sku_missing = 0
    for it in sorted(items, key=lambda x: x["id"]):
        if item_plan[it["id"]]["status"] != "KEEP":
            continue
        mp = model_plan[it["model_id"]]
        brand = by_id[mp["survivor"]]["brand"]
        have = {match_key(brand, mp["canonical"])} | {match_key(by_id[c]["brand"], model_plan[c]["canonical"]) for c in compat[it["id"]]}
        for token in it["sku"].split("-")[1:]:
            if token.upper() in brand_words or not any(ch.isdigit() for ch in token):
                continue
            key = match_key(brand, token)
            if key and key not in have and (brand, key) in model_by_key:
                sku_missing += 1
                fit_rows.append(["old code names a model not in the compatible list", it["category"], brand, model_plan[model_by_key[(brand, key)][0]["id"]]["canonical"], f"{it['sku']} -> add as compatible model of {mp['canonical']}", "proposed (agree?)"])
    sheet = read_sheet_fitment(workbook)
    for text, count in sheet:
        f = parse_fitment(text)
        fit_rows.append(["sheet fitment text", "", " / ".join(f.brands), " / ".join(f.models), f"{text} (x{count})", "REVIEW: " + "; ".join(f.reasons) if f.needs_review else "proposed compatible group (needs your yes)"])
    write_csv("fitment.csv", ["kind", "category", "brand", "models", "detail", "action"], fit_rows)

    # ---- the markdown
    flagged = [m for m in models if model_plan[m["id"]]["status"] == "REVIEW"]
    merge_groups = collections.defaultdict(list)
    for m in models:
        if model_plan[m["id"]]["status"] in ("MERGE", "RENAME"):
            merge_groups[(m["brand"], model_plan[m["id"]]["survivor"])].append(m)
    lines = [
        "# Catalog cleanup review", "",
        "Generated read-only from production. **Nothing has been changed.** Check the lists, tell me what to correct, and only then is the cleanup run.", "",
        "## Summary", "",
        f"- Models: {len(models)} total. {n_ok} already in the standard form, {n_rename} to rename, {n_merge} to merge into another model, {n_review} need your decision.",
        f"- Items: {len(items)} active. {n_item_merge} duplicates to merge into another item (stock lots, purchase lines and sales lines are moved, nothing is lost). {len(keep)} remain.",
        f"- Item codes: {n_sku_std_before} of {len(items)} are in the standard pattern today. After the cleanup {len(sku_rows) - n_sku_review} get a standard code ({n_sku_change} change, {len(sku_rows) - n_sku_review - n_sku_change} already match); {n_sku_review} wait for their model to be decided.",
        f"- Compatible models: {len(shared)} cases where two items (same category, same colour) share a phone - decide one item or two; {sku_missing} old item codes name an extra phone that is missing from the compatible list (it would be lost when codes are rewritten); {len(sheet)} fitment texts in your sheet.", "",
        "Full lists: `catalog_cleanup_review/models.csv`, `items.csv`, `skus.csv`, `fitment.csv`.", "",
        "## 1. Models that need your decision", "",
        "These can't be turned into a trustworthy model name automatically (a colour entered as a model, a cut-off fragment, a typo).", "",
        "| Brand | Current name | Items using it | Why |", "|---|---|---|---|",
    ]
    for m in flagged:
        lines.append(f"| {m['brand']} | `{m['name']}` | {m['items']} | {model_plan[m['id']]['reasons']} |")
    multi = {k: v for k, v in merge_groups.items() if len(v) > 1 or any(model_plan[m["id"]]["status"] == "MERGE" for m in v)}
    lines += ["", f"## 2. Same phone written several ways (will be merged into one model)", "",
              f"{len(multi)} phones. A further {n_rename - sum(1 for v in multi.values() for m in v if model_plan[m['id']]['status'] == 'RENAME')} models only get a tidier name (see `models.csv`).", "",
              "| Brand | Standard name | Spellings merged | Items moved |", "|---|---|---|---|"]
    for (brand, sid), ms in sorted(multi.items(), key=lambda kv: (kv[0][0], model_plan[kv[0][1]]["canonical"])):
        names = ", ".join(f"`{m['name']}`" for m in ms)
        lines.append(f"| {brand} | **{model_plan[sid]['canonical']}** | {names} | {sum(m['items'] for m in ms)} |")
    lines += ["", "## 3. Items that will be merged (same product, two records)", "", "| Category | Keep | Merge into it | Stock moved |", "|---|---|---|---|"]
    for key, members in sorted(groups.items(), key=lambda kv: (item_by_id[kv[1][0]["id"]]["category"], kv[1][0]["sku"])):
        if len(members) < 2:
            continue
        surv = next(m for m in members if item_plan[m["id"]]["status"] == "KEEP")
        others = [m for m in members if m["id"] != surv["id"]]
        lines.append(f"| {surv['category']} | `{surv['sku']}` (stock {surv['stock']}) | " + ", ".join(f"`{o['sku']}` (stock {o['stock']})" for o in others) + f" | {sum(o['stock'] for o in others)} |")
    lines += ["", "## 4. Compatible models: your call", "",
              "Phones that take the same part should be ONE item with the other phones as compatible models. Where today they are two items, "
              "I will not merge them without your yes. Examples (full list in `fitment.csv`):", ""]
    for r in fit_rows[:30]:
        lines.append(f"- {r[0]}: {r[1]} {r[2]} {r[3]} - {r[4]}")
    lines += ["", "## 5. New item codes", "", f"Pattern `CATEGORY-BRAND-MODEL[-VARIANT]`. Category codes: " + ", ".join(f"{k} = `{v}`" for k, v in CATEGORY_CODES.items()) + ".", "",
              "Sample (full old -> new list in `catalog_cleanup_review/skus.csv`):", "", "| Old | New |", "|---|---|"]
    for r in [x for x in sku_rows if x[7] == "change"][:25]:
        lines.append(f"| `{r[1]}` | `{r[2]}` |")
    OUT_MD.write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT_MD} and {OUT_DIR}/*.csv")
    print(f"models: {n_ok} ok / {n_rename} rename / {n_merge} merge / {n_review} review | items to merge: {n_item_merge} | sku change: {n_sku_change}, review: {n_sku_review} | shared-model cases: {len(shared)} | sheet fitment texts: {len(sheet)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workbook", default=DEFAULT_WORKBOOK)
    args = parser.parse_args()
    asyncio.run(main(args.workbook))
