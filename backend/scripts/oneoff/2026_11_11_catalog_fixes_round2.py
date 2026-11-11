"""Catalog fixes, round 2: the odd entries the owner approved (see PRODUCTION_CHANGES_LOG.md #14 and the review lists).

One transaction. Default is a DRY RUN that rolls back; --apply writes.
  * Pixel "9RO" / "9ROXL" (the P of Pro is missing)   -> merged into Pixel 9 Pro / 9 Pro XL
  * Vivo "V40 Lite (YOUNG"                              -> merged into V40 Lite;   "Y51(2020" -> "Y51 (2020)"
  * Samsung "S25 Ultra Grey Titanium"                   -> merged into S25 Ultra (colour Grey)
  * Infinix "NOTE EDGE" and Samsung "Galaxy Note Edge"  -> "Note Edge" (each stays under its own brand)
  * Tecno "SPARKGO" -> "Spark Go";  OnePlus "Ace" -> "Ace 5" (the network tag "5G" is no colour: cleared)
  * Xiaomi "RN13 & Poco C55"                            -> the model becomes "Poco C55"; that dust plug is a
                                                           Redmi Note 13 item that also fits Poco C55
  * hide the unused model "REDMI" and the empty "9PROXLFINGER" item/model
  * remove the wrong "also fits Vivo V60" link on the Redmi 12 TPU case
  * "R-C15" (filed under Xiaomi by mistake) is Realme C15: the model moves to the Realme brand and becomes "C15"
Items that become the same product are merged (stock lots, purchase lines, sales lines move to the survivor, the copy
is hidden). Item codes of every touched item are rewritten to the standard.
Checked before commit: stock lot quantities, ledger totals and purchase/sales line totals unchanged; no duplicate
active product; codes unique and standard; no active item on a hidden model.

    PROD_DSN=postgresql://... python backend/scripts/oneoff/2026_11_11_catalog_fixes_round2.py [--apply]
"""
import asyncio
import collections
import hashlib
import json
import os
import sys
from decimal import Decimal
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.catalog.naming import build_sku, canonical_model_name, is_standard_sku  # noqa: E402

APPLY = "--apply" in sys.argv
BACKUP = Path(__file__).parent / "backups" / "2026_11_11_catalog_fixes_round2.json"

# model id -> (expected current name, brand)
MERGE_MODELS = {247: ("Pixel 9RO", "Google Pixel", 158), 250: ("Pixel 9ROXL", "Google Pixel", 160),
                340: ("V40 Lite (YOUNG", "Vivo", 1460), 410: ("S25 Ultra Grey Titanium", "Samsung", 177)}
RENAME_MODELS = {334: ("Y51(2020", "Y51 (2020)"), 462: ("Galaxy Note Edge", "Note Edge"), 37: ("NOTE EDGE", "Note Edge"),
                 1533: ("SPARKGO", "Spark Go"), 380: ("Ace", "Ace 5"), 289: ("RN13 & Poco C55", "Poco C55")}
HIDE_MODEL_IDS = {1480: "REDMI", 1536: "9PROXLFINGER"}
MOVE_MODEL_ID = 281  # Xiaomi "R-C15" -> Realme "C15" (the owner confirmed it is the Realme C15)


class Abort(Exception):
    pass


def need(cond, msg):
    if not cond:
        raise Abort(msg)


async def snapshot(conn):
    lots = await conn.fetch("select id, qty_received, qty_remaining from stock_lot order by id")
    return {
        "lots": hashlib.md5(json.dumps([(r["id"], str(r["qty_received"]), str(r["qty_remaining"])) for r in lots]).encode()).hexdigest(),
        "ledger": [tuple(map(str, r)) for r in await conn.fetch("select account, sum(debit), sum(credit), count(*) from ledger_entry group by 1 order by 1")],
        "po_lines": tuple(map(str, await conn.fetchrow("select count(*), sum(qty*rate_pkr) from purchase_order_line"))),
        "so_lines": tuple(map(str, await conn.fetchrow("select count(*), sum(qty*rate_pkr) from sales_order_line"))),
        "lots_on_inactive_items": await conn.fetchval("select count(*) from stock_lot sl join item i on i.id=sl.item_id where not i.is_active"),
        "compat_on_inactive_items": await conn.fetchval("select count(*) from item_compatible_model x join item i on i.id=x.item_id where not i.is_active"),
    }


async def main() -> None:
    conn = await asyncpg.connect(os.environ["PROD_DSN"].split("?")[0], ssl=True, timeout=60)
    try:
        try:
            async with conn.transaction():
                print("mode:", "APPLY" if APPLY else "DRY RUN (rolled back)")
                before = await snapshot(conn)
                brands = {r["id"]: r["name"] for r in await conn.fetch("select id, name from brand")}
                models = {r["id"]: dict(r) for r in await conn.fetch("select * from model")}
                items = {r["id"]: dict(r) for r in await conn.fetch(
                    "select i.*, cat.name category, "
                    "(select count(*) from stock_lot x where x.item_id=i.id) lots, "
                    "(select coalesce(sum(x.qty_remaining),0) from stock_lot x where x.item_id=i.id) stock, "
                    "(select count(*) from purchase_order_line x where x.item_id=i.id) pol, "
                    "(select count(*) from sales_order_line x where x.item_id=i.id) sol from item i join category cat on cat.id=i.category_id")}
                compat = collections.defaultdict(set)
                for r in await conn.fetch("select item_id, model_id from item_compatible_model"):
                    compat[r["item_id"]].add(r["model_id"])
                backup = {"model": [models[m] for m in {*MERGE_MODELS, *RENAME_MODELS, *HIDE_MODEL_IDS, *(v[2] for v in MERGE_MODELS.values())}],
                          "item_compatible_model": [[i, m] for i, ms in compat.items() for m in sorted(ms)], "item": list(items.values())}

                # ---------- expected starting state ----------
                for mid, (name, brand, survivor) in MERGE_MODELS.items():
                    need(models[mid]["name"] == name and brands[models[mid]["brand_id"]] == brand and models[mid]["is_active"], f"model {mid} is not {name}")
                    need(models[survivor]["is_active"] and brands[models[survivor]["brand_id"]] == brand, f"survivor model {survivor} missing")
                for mid, (old, _new) in RENAME_MODELS.items():
                    need(models[mid]["name"] == old and models[mid]["is_active"], f"model {mid} is not {old}")
                for mid, old in HIDE_MODEL_IDS.items():
                    need(models[mid]["name"] == old and models[mid]["is_active"], f"model {mid} is not {old}")
                need(models[MOVE_MODEL_ID]["name"] == "R-C15" and brands[models[MOVE_MODEL_ID]["brand_id"]] == "Xiaomi", "R-C15 model changed")
                realme_id = next(i for i, n in brands.items() if n == "Realme")
                need(not [m for m in models.values() if m["brand_id"] == realme_id and m["name"] == "C15"], "Realme already has a model called C15")
                redmi_note13 = 279
                need(models[redmi_note13]["name"] == "Redmi Note 13" and brands[models[redmi_note13]["brand_id"]] == "Xiaomi", "Redmi Note 13 model missing")
                touched_items: set[int] = set()
                changed_model_ids = {*MERGE_MODELS, *(v[2] for v in MERGE_MODELS.values()), *RENAME_MODELS, redmi_note13, MOVE_MODEL_ID}
                # items on models that get a clean code (Reno Z / Pop Lite are accepted as they are)
                for mid in [m["id"] for m in models.values() if m["name"] in ("Reno Z", "Pop Lite") and m["is_active"]]:
                    changed_model_ids.add(mid)
                print("starting state OK")

                async def merge_model(loser: int, survivor: int):
                    await conn.execute("update item set model_id=$1 where model_id=$2", survivor, loser)
                    await conn.execute(
                        "delete from item_compatible_model x using item i where x.item_id=i.id and x.model_id=$1 and (i.model_id=$2 or exists "
                        "(select 1 from item_compatible_model y where y.item_id=x.item_id and y.model_id=$2))", loser, survivor)
                    await conn.execute("update item_compatible_model set model_id=$1 where model_id=$2", survivor, loser)
                    await conn.execute("update model set is_active=false, name=$1 where id=$2", f"{models[loser]['name']} [merged into #{survivor}]", loser)
                    for it in items.values():
                        if it["model_id"] == loser:
                            it["model_id"] = survivor; touched_items.add(it["id"])
                    for ms in compat.values():
                        if loser in ms:
                            ms.discard(loser); ms.add(survivor)
                    models[loser]["is_active"] = False

                async def merge_item(loser: int, survivor: int):
                    L, S = items[loser], items[survivor]
                    for table in ("stock_lot", "purchase_order_line", "sales_order_line"):
                        await conn.execute(f"update {table} set item_id=$1 where item_id=$2", survivor, loser)
                    extra = {m for m in compat[loser] if m != S["model_id"]} - compat[survivor]
                    for mid in sorted(extra):
                        await conn.execute("insert into item_compatible_model (item_id, model_id) values ($1, $2)", survivor, mid)
                    compat[survivor] |= extra
                    await conn.execute("delete from item_compatible_model where item_id=$1", loser)
                    compat[loser] = set()
                    await conn.execute("update item set is_active=false where id=$1", loser)
                    for k in ("lots", "pol", "sol", "stock"):
                        S[k] += L[k]; L[k] = 0
                    L["is_active"] = False
                    touched_items.add(survivor)

                # ---------- 1. hide the empty finger item and the unused models ----------
                finger = [i for i in items.values() if i["model_id"] == 1536 and i["is_active"]]
                need(len(finger) == 1 and finger[0]["lots"] + finger[0]["pol"] + finger[0]["sol"] == 0, "9PROXLFINGER item is not the empty one")
                await conn.execute("update item set is_active=false where id=$1", finger[0]["id"])
                await conn.execute("delete from item_compatible_model where item_id=$1", finger[0]["id"])
                finger[0]["is_active"] = False
                for mid in HIDE_MODEL_IDS:
                    need(not any(i["is_active"] and i["model_id"] == mid for i in items.values()), f"model {mid} still has active items")
                    await conn.execute("delete from item_compatible_model where model_id=$1", mid)
                    await conn.execute("update model set is_active=false where id=$1", mid)
                    models[mid]["is_active"] = False

                # ---------- 2. rename models (before merges: names are free of the survivors' names) ----------
                for mid, (old, new) in RENAME_MODELS.items():
                    clash = [m for m in models.values() if m["brand_id"] == models[mid]["brand_id"] and m["name"] == new and m["id"] != mid]
                    need(not clash, f"another model is already called {new}: {[c['id'] for c in clash]}")
                    await conn.execute("update model set name=$1 where id=$2", new, mid)
                    models[mid]["name"] = new

                await conn.execute("update model set name='C15', brand_id=$1 where id=$2", realme_id, MOVE_MODEL_ID)
                models[MOVE_MODEL_ID].update(name="C15", brand_id=realme_id)

                # ---------- 3. colour / variant fixes on single items ----------
                ace = [i for i in items.values() if i["model_id"] == 380 and i["is_active"]]
                need(len(ace) == 1 and ace[0]["variant"] == "5G", "the Ace item is not as expected")
                await conn.execute("update item set variant=NULL where id=$1", ace[0]["id"]); ace[0]["variant"] = None; touched_items.add(ace[0]["id"])

                grey_item = [i for i in items.values() if i["model_id"] == 177 and i["category"] == "Jun Best Lens Protector" and (i["variant"] or "").upper() == "GREY" and i["is_active"]]
                need(len(grey_item) == 1, "expected exactly one existing S25 Ultra Jun Best 'Grey' item")
                gt = [i for i in items.values() if i["model_id"] == 410 and i["is_active"]]
                need(len(gt) == 1, "expected one 'S25 Ultra Grey Titanium' item")
                await conn.execute("update item set variant=$1 where id=$2", grey_item[0]["variant"], gt[0]["id"]); gt[0]["variant"] = grey_item[0]["variant"]

                # ---------- 4. Poco C55: the dust plug is a Redmi Note 13 item that also fits Poco C55 ----------
                poco = [i for i in items.values() if i["model_id"] == 289 and i["is_active"]]
                need(len(poco) == 1, "expected one item on 'RN13 & Poco C55'")
                await conn.execute("update item set model_id=$1 where id=$2", redmi_note13, poco[0]["id"]); poco[0]["model_id"] = redmi_note13
                await conn.execute("insert into item_compatible_model (item_id, model_id) values ($1, 289) on conflict do nothing", poco[0]["id"])
                compat[poco[0]["id"]].add(289); touched_items.add(poco[0]["id"])

                # ---------- 5. wrong link: Redmi 12 TPU case does not fit a Vivo V60 ----------
                tpu12 = await conn.fetchrow("select i.id from item i join model m on m.id=i.model_id join category c on c.id=i.category_id where i.is_active and c.name='TPU Case' and m.name='Redmi 12'")
                v60 = await conn.fetchrow("select m.id from model m join brand b on b.id=m.brand_id where b.name='Vivo' and m.name='V60' and m.is_active")
                need(tpu12 and v60 and v60["id"] in compat[tpu12["id"]], "the wrong V60 link is not where expected")
                await conn.execute("delete from item_compatible_model where item_id=$1 and model_id=$2", tpu12["id"], v60["id"])
                compat[tpu12["id"]].discard(v60["id"])

                # ---------- 6. merge the duplicate models, then the duplicate products ----------
                for mid, (_n, _b, survivor) in MERGE_MODELS.items():
                    await merge_model(mid, survivor)
                n_item_merge = 0
                groups = collections.defaultdict(list)
                for it in items.values():
                    if it["is_active"]:
                        groups[(it["category_id"], it["model_id"], (it["variant"] or "").strip().upper())].append(it)
                for members in groups.values():
                    if len(members) > 1:
                        surv = max(members, key=lambda x: (x["lots"] + x["pol"] + x["sol"], x["stock"], -x["id"]))
                        for it in sorted(members, key=lambda x: x["id"]):
                            if it["id"] != surv["id"]:
                                await merge_item(it["id"], surv["id"]); n_item_merge += 1
                for ms in compat.values():  # a list never repeats the item's own model
                    pass
                for it in items.values():
                    compat[it["id"]].discard(it["model_id"])
                await conn.execute("delete from item_compatible_model x using item i where x.item_id=i.id and x.model_id=i.model_id")

                # ---------- 7. item codes of every touched item ----------
                for it in items.values():
                    if it["is_active"] and it["model_id"] in changed_model_ids:
                        touched_items.add(it["id"])
                taken = {i["sku"] for i in items.values() if i["id"] not in touched_items}
                new_sku = {}
                for iid in sorted(touched_items):
                    it = items[iid]
                    if not it["is_active"]:
                        continue
                    m = models[it["model_id"]]
                    bname = brands[m["brand_id"]]
                    res = canonical_model_name("Redmi" if bname == "Xiaomi" else bname, m["name"], "Redmi" if bname == "Xiaomi" else None)
                    if res.needs_review:
                        continue
                    base = build_sku(it["category"], bname, m["name"], it["variant"])
                    sku, n = base, 2
                    while sku in taken:
                        sku = f"{base}-{n}"; n += 1
                    taken.add(sku); new_sku[iid] = sku
                changing = [i for i, s in new_sku.items() if items[i]["sku"] != s]
                for i in changing:
                    await conn.execute("update item set sku=$1 where id=$2", f"TMP-{i}", i)
                for i in changing:
                    await conn.execute("update item set sku=$1 where id=$2", new_sku[i], i)

                # ---------- verify ----------
                after = await snapshot(conn)
                for k, v in before.items():
                    need(after[k] == v, f"{k} changed: {v} -> {after[k]}")
                need(not await conn.fetch("select 1 from item where is_active group by category_id, model_id, upper(coalesce(variant,'')) having count(*) > 1"), "duplicate active products remain")
                need(await conn.fetchval("select count(*) from item i join model m on m.id=i.model_id where i.is_active and not m.is_active") == 0, "an active item points at a hidden model")
                need(await conn.fetchval("select count(*) from item_compatible_model x join item i on i.id=x.item_id where x.model_id=i.model_id") == 0, "an item lists its own model as compatible")
                need(not [s for i, s in new_sku.items() if i in changing and not is_standard_sku(s)], "a new code does not match the pattern")
                need(await conn.fetchval("select count(*) from model m join brand b on b.id=m.brand_id where b.name='Realme' and m.name='C15' and m.is_active") == 1, "Realme C15 is not exactly one model")
                print(f"models: {len(MERGE_MODELS)} merged | {len(RENAME_MODELS)} renamed | R-C15 moved to Realme C15 | {len(HIDE_MODEL_IDS)} hidden | 1 empty item hidden")
                print(f"items: {n_item_merge} same-product duplicates merged | {len(changing)} codes rewritten | wrong V60 link removed | Poco C55 linked")
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
