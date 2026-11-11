"""Catalog cleanup: one standard for brands, models, items and item codes (see CLAUDE.md "Catalog naming").

One transaction. Default is a DRY RUN that rolls back; --apply writes. Steps:
  1. brands: rename "Redmi" -> "Xiaomi" (the Redmi / Poco / Mi family); create Honor, Motorola, LG
  2. hide the "models" nothing uses that are really colours / cut-off fragments / bare 4G-5G tags
  3. merge models that are the same phone written several ways, rename every model to the standard
     (the Xiaomi line word stays: "Redmi 13C"; Honor models move to the Honor brand)
  4. merge items that are the same product (same category + phone + colour); stock lots, purchase lines, sales
     lines and compatible phones move to the surviving item, the copy is hidden (never deleted)
  5. merge the "empty twins": two items fitting the same phone where only one holds stock (the empty one's phones
     become compatible models of the stocked one). Pairs where BOTH hold stock are left alone and listed.
  6. phones named only in an old item code (PROT-APPLE-IP12-IP12PRO) become compatible models, so nothing is lost
  7. rewrite every item code to CATEGORY-BRAND-MODEL[-VARIANT] (two passes so the unique constraint never trips)
Checked before commit: every stock lot's quantities, every ledger total, every purchase and sales line total
unchanged; no duplicate active product left; all codes unique; no active item on a hidden model.

    PROD_DSN=postgresql://... python backend/scripts/oneoff/2026_11_11_catalog_cleanup.py [--apply]
"""
import asyncio
import collections
import csv
import hashlib
import json
import os
import sys
from decimal import Decimal
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.catalog.naming import (  # noqa: E402
    BRAND_CODES, CATEGORY_CODES, build_sku, canonical_model_name, is_standard_sku, match_key,
)

APPLY = "--apply" in sys.argv
BACKUP = Path(__file__).parent / "backups" / "2026_11_11_catalog_cleanup.json"
LISTS = Path(__file__).resolve().parent.parent.parent.parent / "catalog_cleanup_review"
NEW_BRANDS = ["Honor", "Motorola", "LG"]


class Abort(Exception):
    pass


def need(cond, msg):
    if not cond:
        raise Abort(msg)


def line_for(old_brand: str):
    return "Redmi" if old_brand == "Redmi" else None


async def snapshot(conn):
    lots = await conn.fetch("select id, qty_received, qty_remaining from stock_lot order by id")
    return {
        "lots": hashlib.md5(json.dumps([(r["id"], str(r["qty_received"]), str(r["qty_remaining"])) for r in lots]).encode()).hexdigest(),
        "lot_count": len(lots),
        "ledger": [tuple(map(str, r)) for r in await conn.fetch("select account, sum(debit), sum(credit), count(*) from ledger_entry group by 1 order by 1")],
        "po_lines": tuple(map(str, await conn.fetchrow("select count(*), sum(qty*rate_pkr) from purchase_order_line"))),
        "so_lines": tuple(map(str, await conn.fetchrow("select count(*), sum(qty*rate_pkr) from sales_order_line"))),
        "lots_on_inactive_items": await conn.fetchval("select count(*) from stock_lot sl join item i on i.id=sl.item_id where not i.is_active"),
        # items that were already hidden before this run may keep their old compatible rows; we only add none to hidden items
        "compat_on_inactive_items": await conn.fetchval("select count(*) from item_compatible_model x join item i on i.id=x.item_id where not i.is_active"),
    }


async def main() -> None:
    conn = await asyncpg.connect(os.environ["PROD_DSN"].split("?")[0], ssl=True, timeout=60)
    try:
        try:
            async with conn.transaction():
                print("mode:", "APPLY" if APPLY else "DRY RUN (rolled back)")
                before = await snapshot(conn)

                # ================= load =================
                brands = {r["name"]: r for r in await conn.fetch("select * from brand")}
                need("Redmi" in brands and "Xiaomi" not in brands, "expected brand Redmi and no brand Xiaomi")
                for b in NEW_BRANDS:
                    need(b not in brands, f"brand {b} already exists")
                brand_name = {r["id"]: r["name"] for r in brands.values()}
                models = {r["id"]: dict(r) for r in await conn.fetch("select * from model")}
                cats = {r["id"]: r["name"] for r in await conn.fetch("select id, name from category")}
                items = {r["id"]: dict(r) for r in await conn.fetch(
                    "select i.id, i.sku, i.variant, i.category_id, i.model_id, i.is_active, "
                    "(select count(*) from stock_lot x where x.item_id=i.id) lots, "
                    "(select coalesce(sum(x.qty_remaining),0) from stock_lot x where x.item_id=i.id) stock, "
                    "(select count(*) from purchase_order_line x where x.item_id=i.id) pol, "
                    "(select count(*) from sales_order_line x where x.item_id=i.id) sol from item i")}
                compat = collections.defaultdict(set)
                for r in await conn.fetch("select item_id, model_id from item_compatible_model"):
                    compat[r["item_id"]].add(r["model_id"])
                backup = {
                    "brand": [dict(r) for r in brands.values()], "model": list(models.values()),
                    "item": list(items.values()), "item_compatible_model": [[i, m] for i, ms in compat.items() for m in sorted(ms)],
                }
                used_models = collections.Counter(i["model_id"] for i in items.values() if i["is_active"])
                compat_refs = collections.Counter(m for ms in compat.values() for m in ms)

                # ================= 1-3: model plan =================
                plan = {}  # model id -> dict(target_brand, name, status, survivor)
                groups = collections.defaultdict(list)
                for m in models.values():
                    old_brand = brand_name[m["brand_id"]]
                    honor = old_brand == "Huawei" and m["name"].upper().startswith("HONOR")
                    target_brand = "Xiaomi" if old_brand == "Redmi" else ("Honor" if honor else old_brand)
                    res = canonical_model_name("Honor" if honor else old_brand, m["name"], line_for(old_brand))
                    if res.needs_review or not res.name:
                        # not a product of any item; if it is only attached as "also fits" it is bad data (a colour, a cut-off
                        # fragment): the link is removed and the model hidden. The item's colour lives in its own colour field.
                        unused = used_models[m["id"]] == 0
                        plan[m["id"]] = dict(target_brand=target_brand, name=m["name"], status="HIDE" if (unused and m["is_active"]) else "LEFT", survivor=m["id"], why="; ".join(res.reasons))
                    else:
                        groups[(target_brand, match_key("Honor" if honor else old_brand, m["name"], line_for(old_brand)))].append((m, res.name, target_brand))
                for (tb, key), members in groups.items():
                    active = [x for x in members if x[0]["is_active"]] or members
                    survivor = max(active, key=lambda x: (used_models[x[0]["id"]] + compat_refs[x[0]["id"]], x[0]["name"] == x[1], -x[0]["id"]))[0]
                    canonical = members[0][1]
                    for m, name, _ in members:
                        if m["id"] == survivor["id"]:
                            plan[m["id"]] = dict(target_brand=tb, name=canonical, status="KEEP", survivor=survivor["id"], why="")
                        else:
                            plan[m["id"]] = dict(target_brand=tb, name=m["name"], status="MERGE", survivor=survivor["id"], why="")
                n_hide = sum(1 for p in plan.values() if p["status"] == "HIDE")
                n_left = [m for m in models.values() if plan[m["id"]]["status"] == "LEFT"]
                n_merge = sum(1 for p in plan.values() if p["status"] == "MERGE")
                n_rename = sum(1 for mid, p in plan.items() if p["status"] == "KEEP" and (p["name"] != models[mid]["name"] or p["target_brand"] != brand_name[models[mid]["brand_id"]] or not models[mid]["is_active"]))

                # ================= apply 1: brands =================
                await conn.execute("update brand set name='Xiaomi' where id=$1", brands["Redmi"]["id"])
                new_brand_id = {"Xiaomi": brands["Redmi"]["id"]}
                for b in NEW_BRANDS:
                    new_brand_id[b] = await conn.fetchval("insert into brand (name, is_active) values ($1, true) returning id", b)
                for n_, r in brands.items():
                    new_brand_id.setdefault(n_, r["id"])
                brand_by_id = {i: n_ for n_, i in new_brand_id.items() if n_ != "Redmi"}  # Redmi is now Xiaomi

                # ================= apply 2: hide unused odd models =================
                n_detached = 0
                for mid, p in plan.items():
                    if p["status"] == "HIDE":
                        n_detached += int((await conn.execute("delete from item_compatible_model where model_id=$1", mid)).split()[-1])
                        await conn.execute("update model set is_active=false where id=$1", mid)
                        models[mid]["is_active"] = False
                        for ms in compat.values():
                            ms.discard(mid)

                # ================= apply 3: merge + rename models =================
                for mid, p in sorted(plan.items()):
                    if p["status"] != "MERGE":
                        continue
                    s = p["survivor"]
                    await conn.execute("update item set model_id=$1 where model_id=$2", s, mid)
                    await conn.execute(
                        "delete from item_compatible_model x using item i where x.item_id=i.id and x.model_id=$1 and (i.model_id=$2 or exists "
                        "(select 1 from item_compatible_model y where y.item_id=x.item_id and y.model_id=$2))", mid, s)
                    await conn.execute("update item_compatible_model set model_id=$1 where model_id=$2", s, mid)
                    await conn.execute("update model set is_active=false, name=$1 where id=$2", f"{models[mid]['name']} [merged into #{s}]", mid)
                    for it in items.values():
                        if it["model_id"] == mid:
                            it["model_id"] = s
                    for ms in compat.values():
                        if mid in ms:
                            ms.discard(mid)
                            ms.add(s)
                for mid, p in sorted(plan.items()):
                    if p["status"] in ("KEEP", "LEFT", "HIDE"):
                        await conn.execute("update model set name=$1, brand_id=$2, is_active=$3 where id=$4", p["name"], new_brand_id[p["target_brand"]],
                                           True if p["status"] == "KEEP" else models[mid]["is_active"], mid)
                        models[mid].update(name=p["name"], brand_id=new_brand_id[p["target_brand"]])
                        if p["status"] == "KEEP":
                            models[mid]["is_active"] = True
                for it in items.values():  # a compatible list never repeats the item's own model
                    compat[it["id"]].discard(it["model_id"])
                await conn.execute("delete from item_compatible_model x using item i where x.item_id=i.id and x.model_id=i.model_id")

                # ================= apply 4-5: merge items =================
                def history(it):
                    return it["lots"] + it["pol"] + it["sol"]

                async def merge_item(loser, survivor, add_loser_model: bool):
                    L, S = items[loser], items[survivor]
                    for table in ("stock_lot", "purchase_order_line", "sales_order_line"):
                        await conn.execute(f"update {table} set item_id=$1 where item_id=$2", survivor, loser)
                    extra = set(compat[loser]) | ({L["model_id"]} if add_loser_model else set())
                    extra.discard(S["model_id"])
                    # an unclear model (colour, fragment, no number) is never spread onto another item as "also fits"
                    extra = {m for m in extra if plan[m]["status"] not in ("LEFT", "HIDE")}
                    for mid in sorted(extra - compat[survivor]):
                        await conn.execute("insert into item_compatible_model (item_id, model_id) values ($1, $2)", survivor, mid)
                    compat[survivor] |= extra
                    await conn.execute("delete from item_compatible_model where item_id=$1", loser)
                    compat[loser] = set()
                    await conn.execute("update item set is_active=false where id=$1", loser)
                    S["lots"] += L["lots"]; S["pol"] += L["pol"]; S["sol"] += L["sol"]; S["stock"] += L["stock"]
                    L["lots"] = L["pol"] = L["sol"] = 0; L["stock"] = Decimal(0); L["is_active"] = False

                same_key = collections.defaultdict(list)
                for it in items.values():
                    if it["is_active"]:
                        same_key[(it["category_id"], it["model_id"], (it["variant"] or "").strip().upper())].append(it)
                n_item_merge = 0
                for members in same_key.values():
                    if len(members) > 1:
                        surv = max(members, key=lambda x: (history(x), x["stock"], -x["id"]))
                        for it in sorted(members, key=lambda x: x["id"]):
                            if it["id"] != surv["id"]:
                                await merge_item(it["id"], surv["id"], False)
                                n_item_merge += 1

                twin_rows = []
                n_twins = 0
                for _ in range(500):
                    overlap = collections.defaultdict(set)
                    for it in items.values():
                        if it["is_active"]:
                            for mid in {it["model_id"]} | compat[it["id"]]:
                                overlap[(it["category_id"], mid, (it["variant"] or "").strip().upper())].add(it["id"])
                    pick = None
                    for key, ids in sorted(overlap.items(), key=lambda kv: (kv[0][0], kv[0][1], kv[0][2])):
                        if len(ids) < 2:
                            continue
                        stocked = [i for i in ids if items[i]["stock"] > 0]
                        if len(stocked) == 1:
                            empties = sorted(i for i in ids if i != stocked[0])
                            pick = (empties[0], stocked[0], key)
                            break
                    if not pick:
                        break
                    L, S, key = pick
                    twin_rows.append([cats[items[L]["category_id"]], items[L]["sku"], items[S]["sku"], models[key[1]]["name"]])
                    await merge_item(L, S, True)
                    n_twins += 1
                still_shared = []
                overlap = collections.defaultdict(set)
                for it in items.values():
                    if it["is_active"]:
                        for mid in {it["model_id"]} | compat[it["id"]]:
                            overlap[(it["category_id"], mid, (it["variant"] or "").strip().upper())].add(it["id"])
                for key, ids in sorted(overlap.items()):
                    if len(ids) > 1:
                        still_shared.append([cats[key[0]], brand_by_id[models[key[1]]["brand_id"]], models[key[1]]["name"],
                                             " | ".join(f"{items[i]['sku']} (stock {items[i]['stock']})" for i in sorted(ids))])

                # ================= apply 6: phones named only in an old item code =================
                active_models = collections.defaultdict(list)
                for m in models.values():
                    if m["is_active"] and plan[m["id"]]["status"] in ("KEEP", "LEFT"):
                        bname = brand_by_id[m["brand_id"]]
                        active_models[(bname, match_key("Redmi" if bname == "Xiaomi" else bname, m["name"], "Redmi" if bname == "Xiaomi" else None))].append(m["id"])
                sku_compat = []
                skip_words = {w for ws in __import__("src.catalog.naming", fromlist=["BRAND_PREFIXES"]).BRAND_PREFIXES.values() for w in ws} | {"PROT", "DPLUG", "DUST", "TPU", "OG"}
                for it in sorted(items.values(), key=lambda x: x["id"]):
                    if not it["is_active"]:
                        continue
                    bname = brand_by_id[models[it["model_id"]]["brand_id"]]
                    have = {it["model_id"]} | compat[it["id"]]
                    for token in it["sku"].split("-")[1:]:
                        if token.upper() in skip_words or not any(ch.isdigit() for ch in token):
                            continue
                        key = (bname, match_key("Redmi" if bname == "Xiaomi" else bname, token, "Redmi" if bname == "Xiaomi" else None))
                        for mid in active_models.get(key, [])[:1]:
                            if mid not in have:
                                await conn.execute("insert into item_compatible_model (item_id, model_id) values ($1, $2)", it["id"], mid)
                                compat[it["id"]].add(mid); have.add(mid)
                                sku_compat.append([it["sku"], models[mid]["name"]])

                # ================= apply 7: item codes =================
                taken = {i["sku"] for i in items.values() if not i["is_active"]}
                new_sku = {}
                kept_old = []
                for it in sorted(items.values(), key=lambda x: x["id"]):
                    if not it["is_active"]:
                        continue
                    m = models[it["model_id"]]
                    bname = brand_by_id[m["brand_id"]]
                    flagged = canonical_model_name("Redmi" if bname == "Xiaomi" else bname, m["name"], "Redmi" if bname == "Xiaomi" else None).needs_review
                    try:
                        base = build_sku(cats[it["category_id"]], bname, m["name"], it["variant"]) if not flagged else None
                    except KeyError:
                        base = None
                    if not base:
                        new_sku[it["id"]] = it["sku"]; taken.add(it["sku"]); kept_old.append(it["sku"])
                        continue
                    sku, n = base, 2
                    while sku in taken:
                        sku = f"{base}-{n}"; n += 1
                    taken.add(sku); new_sku[it["id"]] = sku
                changing = [i for i, s in new_sku.items() if items[i]["sku"] != s]
                for i in changing:
                    await conn.execute("update item set sku=$1 where id=$2", f"TMP-{i}", i)
                for i in changing:
                    await conn.execute("update item set sku=$1 where id=$2", new_sku[i], i)

                # ================= verify =================
                after = await snapshot(conn)
                for k in ("lots", "lot_count", "ledger", "po_lines", "so_lines", "lots_on_inactive_items", "compat_on_inactive_items"):
                    need(after[k] == before[k], f"{k} changed: {before[k]} -> {after[k]}")
                dup = await conn.fetch("select category_id, model_id, upper(coalesce(variant,'')) v, count(*) from item where is_active group by 1,2,3 having count(*) > 1")
                need(not dup, f"duplicate active products remain: {[tuple(r) for r in dup][:5]}")
                bad = await conn.fetchval("select count(*) from item i join model m on m.id=i.model_id where i.is_active and not m.is_active")
                need(bad == 0, f"{bad} active items point at a hidden model")
                need(await conn.fetchval("select count(*) from item_compatible_model x join item i on i.id=x.item_id where x.model_id=i.model_id") == 0, "an item lists its own model as compatible")
                need(await conn.fetchval("select count(*) from stock_lot sl join item i on i.id=sl.item_id where not i.is_active") == before["lots_on_inactive_items"], "lots on hidden items changed")
                need(not [s for i, s in new_sku.items() if i in changing and not is_standard_sku(s)], "a new code does not match the pattern")
                n_active = await conn.fetchval("select count(*) from item where is_active")

                LISTS.mkdir(exist_ok=True)
                for name, header, rows in (
                    ("cleanup_shared_phone_both_stocked.csv", ["category", "brand", "model", "items (stock)"], still_shared),
                    ("cleanup_empty_twins_merged.csv", ["category", "merged_item", "into_item", "shared_model"], twin_rows),
                    ("cleanup_models_left_for_you.csv", ["brand", "model", "items", "why"], [[brand_by_id[m["brand_id"]], m["name"], used_models[m["id"]], plan[m["id"]]["why"]] for m in n_left]),
                    ("cleanup_compatible_from_old_codes.csv", ["item_code_before", "added_compatible_model"], sku_compat),
                ):
                    with open(LISTS / name, "w", newline="") as fh:
                        w = csv.writer(fh); w.writerow(header); w.writerows(rows)
                print(f"brands: Redmi -> Xiaomi, created {', '.join(NEW_BRANDS)}")
                print(f"models: {n_hide} hidden (odd ones no item uses; {n_detached} bad 'also fits' links removed) | {len(n_left)} left for you | {n_merge} merged | {n_rename} renamed or moved")
                print(f"items: {n_item_merge} same-product duplicates merged | {n_twins} empty twins merged | {len(still_shared)} shared-phone cases left (both hold stock) | {len(sku_compat)} compatible phones kept from old codes")
                print(f"item codes: {len(changing)} rewritten | {len(kept_old)} kept (model still undecided) | active items now {n_active}")
                print("verified: stock lots, ledger totals, purchase/sales line totals unchanged; no duplicate products; codes unique and standard")
                if APPLY:
                    BACKUP.write_text(json.dumps(backup, indent=1, default=str))
                    print("backup written:", BACKUP)
                else:
                    raise Abort("dry run - rolling back")
        except Abort as exc:
            if "dry run" not in str(exc):
                print("ABORTED, nothing written:", exc)
                sys.exit(1)
            print("(dry run rolled back - nothing written)")
    finally:
        await conn.close()


asyncio.run(main())
