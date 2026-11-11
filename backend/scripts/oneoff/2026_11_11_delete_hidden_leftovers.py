"""Permanently delete the hidden catalog leftovers nothing uses any more.

After the catalog cleanup, merged-away duplicates and junk entries were only HIDDEN (is_active = false). This deletes
the hidden rows that nothing points at:
  * hidden items with no stock lot, purchase line or sales line (their compatible-model rows go with them)
  * then hidden models that no item and no compatible-model row points at
Active rows are never touched, and hidden rows that history still references stay hidden.
Every deleted row is first written to backups/2026_11_11_hidden_leftovers_deleted.json (and the earlier cleanup backups
hold the same rows), so anything can be put back by hand.

One transaction; default is a DRY RUN that rolls back; --apply writes.
    PROD_DSN=postgresql://... python backend/scripts/oneoff/2026_11_11_delete_hidden_leftovers.py [--apply]
"""
import asyncio
import hashlib
import json
import os
import sys
from pathlib import Path

import asyncpg

APPLY = "--apply" in sys.argv
BACKUP = Path(__file__).parent / "backups" / "2026_11_11_hidden_leftovers_deleted.json"
EXPECT_ITEMS = 73  # from the read-only count; the script refuses to run if production differs


class Abort(Exception):
    pass


def need(cond, msg):
    if not cond:
        raise Abort(msg)


UNREF_ITEM = ("not i.is_active and not exists (select 1 from stock_lot x where x.item_id=i.id) "
              "and not exists (select 1 from purchase_order_line x where x.item_id=i.id) "
              "and not exists (select 1 from sales_order_line x where x.item_id=i.id)")
UNREF_MODEL = ("not m.is_active and not exists (select 1 from item i where i.model_id=m.id) "
               "and not exists (select 1 from item_compatible_model x where x.model_id=m.id)")


async def snapshot(conn):
    lots = await conn.fetch("select id, qty_received, qty_remaining from stock_lot order by id")
    return {
        "lots": hashlib.md5(json.dumps([(r["id"], str(r["qty_received"]), str(r["qty_remaining"])) for r in lots]).encode()).hexdigest(),
        "ledger": [tuple(map(str, r)) for r in await conn.fetch("select account, sum(debit), sum(credit), count(*) from ledger_entry group by 1 order by 1")],
        "po_lines": tuple(map(str, await conn.fetchrow("select count(*), sum(qty*rate_pkr) from purchase_order_line"))),
        "so_lines": tuple(map(str, await conn.fetchrow("select count(*), sum(qty*rate_pkr) from sales_order_line"))),
        "active_items": await conn.fetchval("select count(*) from item where is_active"),
        "active_models": await conn.fetchval("select count(*) from model where is_active"),
        "active_compat": await conn.fetchval("select count(*) from item_compatible_model x join item i on i.id=x.item_id where i.is_active"),
    }


async def main() -> None:
    conn = await asyncpg.connect(os.environ["PROD_DSN"].split("?")[0], ssl=True, timeout=60)
    try:
        try:
            async with conn.transaction():
                print("mode:", "APPLY" if APPLY else "DRY RUN (rolled back)")
                before = await snapshot(conn)
                items = await conn.fetch(f"select i.* from item i where {UNREF_ITEM} order by i.id")
                need(len(items) == EXPECT_ITEMS, f"found {len(items)} unreferenced hidden items, expected {EXPECT_ITEMS}")
                item_ids = [r["id"] for r in items]
                compat_rows = await conn.fetch("select * from item_compatible_model where item_id = any($1::int[])", item_ids)
                backup = {"item": [dict(r) for r in items], "item_compatible_model": [dict(r) for r in compat_rows]}
                need((await conn.execute("delete from item_compatible_model where item_id = any($1::int[])", item_ids)).endswith(str(len(compat_rows))), "compat delete count")
                need(await conn.execute("delete from item where id = any($1::int[])", item_ids) == f"DELETE {len(items)}", "item delete count")
                models = await conn.fetch(f"select m.* from model m where {UNREF_MODEL} order by m.id")
                model_ids = [r["id"] for r in models]
                backup["model"] = [dict(r) for r in models]
                need(await conn.execute("delete from model where id = any($1::int[])", model_ids) == f"DELETE {len(models)}", "model delete count")

                after = await snapshot(conn)
                for k, v in before.items():
                    need(after[k] == v, f"{k} changed: {v} -> {after[k]}")
                left_items = await conn.fetchval("select count(*) from item where not is_active")
                left_models = await conn.fetchval("select count(*) from model where not is_active")
                need(await conn.fetchval(f"select count(*) from item i where {UNREF_ITEM}") == 0, "an unreferenced hidden item is left")
                need(await conn.fetchval(f"select count(*) from model m where {UNREF_MODEL}") == 0, "an unreferenced hidden model is left")
                print(f"deleted {len(items)} hidden items (+ {len(compat_rows)} compatible-model rows) and {len(models)} hidden models")
                print(f"hidden rows kept because history still points at them: {left_items} items, {left_models} models")
                print("verified: active items/models/links, stock lots, ledger and purchase/sales totals all unchanged")
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
