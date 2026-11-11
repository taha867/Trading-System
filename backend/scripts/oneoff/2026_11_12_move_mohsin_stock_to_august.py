"""Move every Mohsin purchase (the stock received from Mohsin) to 25 August 2026.

The owner's decision: all the stock we got from Mohsin was received in August (the Mohsin balance sheet is dated 25-8-2026);
the app had 8 Sept - 9 Oct from the way it was loaded. Only DATES change - never an amount, quantity, cost or party.

In ONE transaction (default is a dry run that rolls back; --apply writes):
  1. asserts the starting state (29 Mohsin purchase orders, 972 lots, 972 receipt movements, 58 purchase_order ledger rows,
     972 stock_lot ledger rows, no sale of this stock dated before the new date);
  2. backs up every old date to backups/2026_11_12_mohsin_to_august.json (apply mode);
  3. sets purchase_order.order_date, stock_lot.received_date, the 'receipt' stock movements and the purchase_order /
     stock_lot ledger rows of those orders to the new date;
  4. verifies lots (qty, value), movements (count, qty), every ledger total and every party / account balance are identical,
     and nothing now dated 25 Aug 2026 is anything else.

    PROD_DSN=postgresql://... python backend/scripts/oneoff/2026_11_12_move_mohsin_stock_to_august.py [--apply]
"""
import asyncio
import json
import os
import sys
from datetime import date
from pathlib import Path

import asyncpg

APPLY = "--apply" in sys.argv
NEW = date(2026, 8, 25)
BACKUP = Path(__file__).parent / "backups" / "2026_11_12_mohsin_to_august.json"
POS = "(select id from purchase_order where source = 'mohsin')"
LOTS = f"(select l.id from stock_lot l join purchase_order_line pl on pl.id = l.purchase_order_line_id where pl.purchase_order_id in {POS})"


class Abort(Exception):
    pass


def need(cond, msg):
    if not cond:
        raise Abort(msg)


async def fingerprint(conn):
    return {
        "lots": tuple((await conn.fetchrow("select count(*), sum(qty_received), sum(qty_remaining), sum(qty_remaining * landed_cost_pkr) from stock_lot")).values()),
        "moves": tuple((await conn.fetchrow("select count(*), sum(qty_delta) from stock_movement")).values()),
        "ledger": [tuple(r.values()) for r in await conn.fetch("select account, reference_type, count(*), sum(debit), sum(credit) from ledger_entry group by 1, 2 order by 1, 2")],
        "parties": [tuple(r.values()) for r in await conn.fetch("select party_id, sum(debit - credit) from ledger_entry where party_id is not null group by 1 order by 1")],
        "accounts": [tuple(r.values()) for r in await conn.fetch("select payment_account_id, sum(debit - credit) from ledger_entry where payment_account_id is not null group by 1 order by 1")],
        "po_lines": tuple((await conn.fetchrow("select count(*), sum(qty), sum(qty * rate_pkr) from purchase_order_line")).values()),
    }


async def main():
    conn = await asyncpg.connect(os.environ["PROD_DSN"].split("?")[0], ssl=True, timeout=30)
    tx = conn.transaction()
    await tx.start()
    try:
        need(await conn.fetchval(f"select count(*) from {POS} x") == 29, "expected 29 Mohsin purchase orders")
        need(await conn.fetchval(f"select count(*) from {LOTS} x") == 972, "expected 972 lots")
        need(await conn.fetchval(f"select count(*) from stock_movement where movement_type = 'receipt' and stock_lot_id in {LOTS}") == 972, "expected 972 receipt movements")
        need(await conn.fetchval(f"select count(*) from ledger_entry where reference_type = 'purchase_order' and reference_id in {POS}") == 58, "expected 58 purchase_order ledger rows")
        need(await conn.fetchval(f"select count(*) from ledger_entry where reference_type = 'stock_lot' and reference_id in {LOTS}") == 972, "expected 972 stock_lot ledger rows")
        need(await conn.fetchval(f"select count(*) from stock_movement where movement_type = 'sale' and movement_date < $1 and stock_lot_id in {LOTS}", NEW) == 0, "a sale of this stock is older than the new date")
        need(await conn.fetchval("select count(*) from purchase_order where order_date = $1", NEW) == 0, "something is already dated the new date")
        before = await fingerprint(conn)

        if APPLY:
            BACKUP.parent.mkdir(exist_ok=True)
            BACKUP.write_text(json.dumps({
                "new_date": str(NEW),
                "purchase_order": {str(r["id"]): str(r["order_date"]) for r in await conn.fetch(f"select id, order_date from purchase_order where id in {POS}")},
                "stock_lot": {str(r["id"]): str(r["received_date"]) for r in await conn.fetch(f"select id, received_date from stock_lot where id in {LOTS}")},
                "stock_movement_receipt": {str(r["id"]): str(r["movement_date"]) for r in await conn.fetch(f"select id, movement_date from stock_movement where movement_type = 'receipt' and stock_lot_id in {LOTS}")},
                "ledger_entry": {str(r["id"]): str(r["entry_date"]) for r in await conn.fetch(f"select id, entry_date from ledger_entry where (reference_type = 'purchase_order' and reference_id in {POS}) or (reference_type = 'stock_lot' and reference_id in {LOTS})")},
            }, indent=0))

        n = [
            await conn.execute(f"update purchase_order set order_date = $1 where id in {POS}", NEW),
            await conn.execute(f"update stock_lot set received_date = $1 where id in {LOTS}", NEW),
            await conn.execute(f"update stock_movement set movement_date = $1 where movement_type = 'receipt' and stock_lot_id in {LOTS}", NEW),
            await conn.execute(f"update ledger_entry set entry_date = $1 where reference_type = 'purchase_order' and reference_id in {POS}", NEW),
            await conn.execute(f"update ledger_entry set entry_date = $1 where reference_type = 'stock_lot' and reference_id in {LOTS}", NEW),
        ]
        need(n == ["UPDATE 29", "UPDATE 972", "UPDATE 972", "UPDATE 58", "UPDATE 972"], f"unexpected update counts {n}")

        after = await fingerprint(conn)
        need(before == after, "a total changed - only dates may change")
        need(await conn.fetchval("select count(*) from purchase_order where order_date = $1", NEW) == 29, "wrong number of orders on the new date")
        need(await conn.fetchval("select count(*) from stock_lot where received_date = $1", NEW) == 972, "wrong number of lots on the new date")
        print(f"{'APPLY' if APPLY else 'DRY RUN'}: moved 29 Mohsin purchase orders, 972 lots / receipts, 58 + 972 ledger rows to {NEW}; "
              f"all totals, balances and stock identical")
        if APPLY:
            await tx.commit(); print("committed")
        else:
            await tx.rollback(); print("rolled back (dry run) - nothing was changed")
    except Abort as e:
        await tx.rollback(); print(f"ABORTED, nothing written: {e}"); sys.exit(1)
    except BaseException:
        await tx.rollback(); raise
    finally:
        await conn.close()


asyncio.run(main())
