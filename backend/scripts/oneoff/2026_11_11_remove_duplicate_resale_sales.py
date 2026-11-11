"""Remove the 10 duplicate "resale" sales and put the stock back right.

Those 10 sales orders were created from the Local Purchase tab's "Sold To" column. Every one duplicates a line that
is already on the Credit Sale tab (at the purchase price Rs 90/52 instead of the sale price Rs 95/52), so customer
balances were Rs 8,830 too high and the stock was used twice; #49 even took 10 pieces of real China stock (lot 630).

What this does, in ONE transaction (default is a dry run that rolls back; --apply writes):
  1. asserts the exact starting state (ids, parties, dates, qty, rate, lots, movements, ledger rows, balances);
  2. backs up every row it will delete to backups/2026_11_11_duplicate_resales.json (apply mode);
  3. deletes the 10 sales (line-lots -> lines -> orders), their 10 Accounts Receivable ledger rows and their
     10 'sale' stock movements, and gives the consumed quantities back to their lots;
  4. re-points invoice 29's iPhone 15 and iPhone 16 Pro Max lines (sales order #27) from the China-stock lots they
     took (628, 630 @ Rs 82.51) to the locally bought lots (1070, 1074 @ Rs 90), which is where those pieces came from;
  5. verifies the result and rolls back if anything is off.

    PROD_DSN=postgresql://... python backend/scripts/oneoff/2026_11_11_remove_duplicate_resale_sales.py [--apply]
"""
import asyncio
import json
import os
import sys
from decimal import Decimal
from pathlib import Path

import asyncpg

APPLY = "--apply" in sys.argv
BACKUP = Path(__file__).parent / "backups" / "2026_11_11_duplicate_resales.json"

# sales_order id -> (party name, order date, sku, qty, rate, stock lot, ledger_entry id, stock_movement id)
DUPES = {
    26: ("Shoaib Mobile, Jhang", "2026-09-25", "DUST-SAMSUNG-GALAXYS26ULTRA", 5, 90, 992, 1491, 1130),
    44: ("DREAM MOB SARGODAH", "2026-09-07", "OG G-SAMSUNG-GALAXYA16", 40, 52, 1038, 1684, 1316),
    45: ("Shoaib Mobile, Jhang", "2026-09-25", "DPLUG-IPHONE15", 10, 90, 1070, 1718, 1349),
    46: ("Shoaib Mobile, Jhang", "2026-09-25", "DUST-REDMI-NOTE15", 5, 90, 1071, 1720, 1351),
    47: ("Shoaib Mobile, Jhang", "2026-09-25", "DUST-IPHONE-IPHONE13PRO", 10, 90, 1072, 1722, 1353),
    48: ("Shoaib Mobile, Jhang", "2026-09-25", "DUST-INFINIX-SMART20", 10, 90, 1073, 1724, 1355),
    49: ("Shoaib Mobile, Jhang", "2026-09-25", "DPLUG-IPHONE16PROMAX", 10, 90, 630, 1726, 1357),
    50: ("Shoaib Mobile, Jhang", "2026-09-25", "DUST-VIVO-V70", 5, 90, 1075, 1728, 1359),
    51: ("Shoaib Mobile, Jhang", "2026-09-25", "DUST-VIVO-V70FE", 10, 90, 1076, 1730, 1361),
    52: ("Shoaib Mobile, Jhang", "2026-09-25", "DUST-VIVO-Y500", 10, 90, 1077, 1732, 1363),
}
# Invoice 29 (sales order #27): (sales_order_line_lot id, stock movement id, sku, China lot taken, local lot to use)
REPOINT = [(133, 1145, "DPLUG-IPHONE16PROMAX", 630, 1074), (147, 1159, "DPLUG-IPHONE15", 628, 1070)]
LOCAL_COST = Decimal("90.00")
EXPECT_REMAINING_ORDERS = 28
EXPECT_AR_DEBITS_AFTER = Decimal("1142377.00")
EXPECT_PARTY_DEBIT_AFTER = {"Shoaib Mobile, Jhang": Decimal("94600.00"), "DREAM MOB SARGODAH": Decimal("13770.00")}


class Abort(Exception):
    pass


def need(cond, msg):
    if not cond:
        raise Abort(msg)


async def lot_mismatches(conn):
    """Lots whose qty_remaining differs from the sum of their stock movements (receipt + sales + adjustments)."""
    return await conn.fetch(
        "select sl.id from stock_lot sl left join stock_movement m on m.stock_lot_id = sl.id "
        "group by sl.id having sl.qty_remaining <> coalesce(sum(m.qty_delta), 0) order by sl.id"
    )


async def main() -> None:
    conn = await asyncpg.connect(os.environ["PROD_DSN"].split("?")[0], ssl=True, timeout=30)
    ids = list(DUPES)
    try:
        try:
            async with conn.transaction():
                print("mode:", "APPLY" if APPLY else "DRY RUN (rolled back)")

                # ---- 1. starting state -------------------------------------------------------------------
                rows = await conn.fetch(
                    "select so.id, p.name, so.order_date::text d, i.sku, l.qty, l.rate_pkr, l.id line_id, "
                    "(select count(*) from sales_order_line x where x.sales_order_id = so.id) n_lines "
                    "from sales_order so join party p on p.id = so.party_id "
                    "join sales_order_line l on l.sales_order_id = so.id join item i on i.id = l.item_id "
                    "where so.id = any($1::int[]) order by so.id", ids)
                need(len(rows) == 10 and all(r["n_lines"] == 1 for r in rows), f"expected 10 single-line sales, got {len(rows)}")
                for r in rows:
                    name, d, sku, qty, rate, lot, led, mov = DUPES[r["id"]]
                    need((r["name"], r["d"], r["sku"], r["qty"], r["rate_pkr"]) == (name, d, sku, Decimal(qty), Decimal(rate)),
                         f"sales order {r['id']} is not what was expected: {dict(r)}")
                    need(r["id"] != 27 and not r["id"] in (5, 27), "refusing to touch a Credit Sale order")
                line_ids = [r["line_id"] for r in rows]
                cons = await conn.fetch("select * from sales_order_line_lot where sales_order_line_id = any($1::int[]) order by id", line_ids)
                need(len(cons) == 10, f"expected 10 line-lot rows, got {len(cons)}")
                by_line = {c["sales_order_line_id"]: c for c in cons}
                for r in rows:
                    c = by_line[r["line_id"]]
                    need(c["stock_lot_id"] == DUPES[r["id"]][5] and c["qty_consumed"] == r["qty"], f"unexpected lot use for order {r['id']}")
                ledger = await conn.fetch("select * from ledger_entry where id = any($1::int[]) order by id", [d[6] for d in DUPES.values()])
                need(len(ledger) == 10 and all(l["account"] == "Accounts Receivable" and l["reference_type"] == "sales_order"
                                               and DUPES[l["reference_id"]][6] == l["id"] and l["credit"] == 0 for l in ledger), "ledger rows differ")
                need(sum(l["debit"] for l in ledger) == Decimal("8830.00"), "ledger total is not 8,830")
                other_ledger = await conn.fetchval("select count(*) from ledger_entry where reference_type = 'sales_order' and reference_id = any($1::int[])", ids)
                need(other_ledger == 10, f"{other_ledger} ledger rows reference these orders (expected exactly 10)")
                moves = await conn.fetch("select * from stock_movement where id = any($1::int[]) order by id", [d[7] for d in DUPES.values()])
                need(len(moves) == 10 and all(m["movement_type"] == "sale" and m["qty_delta"] == -DUPES[next(k for k, v in DUPES.items() if v[7] == m["id"])][3]
                                              and m["stock_lot_id"] == DUPES[next(k for k, v in DUPES.items() if v[7] == m["id"])][5] for m in moves), "stock movements differ")

                rp = {}
                for lot_line_id, mov_id, sku, china_lot, local_lot in REPOINT:
                    x = await conn.fetchrow("select x.*, i.sku, l.sales_order_id from sales_order_line_lot x join sales_order_line l on l.id = x.sales_order_line_id join item i on i.id = l.item_id where x.id = $1", lot_line_id)
                    need(x and x["sales_order_id"] == 27 and x["sku"] == sku and x["stock_lot_id"] == china_lot and x["qty_consumed"] == 10
                         and x["unit_cost_pkr"] == Decimal("82.51"), f"invoice 29 line-lot {lot_line_id} is not as expected: {dict(x) if x else None}")
                    m = await conn.fetchrow("select * from stock_movement where id = $1", mov_id)
                    need(m and m["stock_lot_id"] == china_lot and m["movement_type"] == "sale" and m["qty_delta"] == -10, f"movement {mov_id} differs")
                    lot = await conn.fetchrow("select sl.*, po.source, i.sku from stock_lot sl join item i on i.id = sl.item_id join purchase_order_line pl on pl.id = sl.purchase_order_line_id join purchase_order po on po.id = pl.purchase_order_id where sl.id = $1", local_lot)
                    need(lot["source"] == "local" and lot["sku"] == sku and lot["qty_received"] == 10 and lot["landed_cost_pkr"] == LOCAL_COST, f"local lot {local_lot} differs")
                    rp[lot_line_id] = x

                debit_before = await conn.fetchval("select sum(debit) from ledger_entry where account = 'Accounts Receivable'")
                party_before = {r["name"]: r["d"] for r in await conn.fetch("select p.name, sum(l.debit) d from party p join ledger_entry l on l.party_id = p.id where l.account = 'Accounts Receivable' and p.name = any($1::text[]) group by 1", list(EXPECT_PARTY_DEBIT_AFTER))}
                need(debit_before - EXPECT_AR_DEBITS_AFTER == Decimal("8830.00"), f"AR debits now {debit_before}, expected 1,151,207.00")
                need(party_before == {"Shoaib Mobile, Jhang": Decimal("101350.00"), "DREAM MOB SARGODAH": Decimal("15850.00")}, f"party balances differ: {party_before}")
                mismatch_before = [r["id"] for r in await lot_mismatches(conn)]
                print("starting state OK | AR debits", debit_before, "| lots with a stock mismatch before:", mismatch_before)

                # ---- 2. backup ---------------------------------------------------------------------------
                lots_before = await conn.fetch("select * from stock_lot where id = any($1::int[])",
                                               sorted({d[5] for d in DUPES.values()} | {r[3] for r in REPOINT} | {r[4] for r in REPOINT}))
                backup = {
                    "sales_order": [dict(r) for r in await conn.fetch("select * from sales_order where id = any($1::int[])", ids)],
                    "sales_order_line": [dict(r) for r in await conn.fetch("select * from sales_order_line where id = any($1::int[])", line_ids)],
                    "sales_order_line_lot": [dict(c) for c in cons],
                    "ledger_entry": [dict(l) for l in ledger], "stock_movement": [dict(m) for m in moves],
                    "stock_lot_before": [dict(l) for l in lots_before],
                    "invoice29_line_lots_before": [dict(x) for x in rp.values()],
                }
                if APPLY:
                    BACKUP.write_text(json.dumps(backup, indent=2, default=str))
                    print("backup written:", BACKUP)

                # ---- 3. remove the duplicates ------------------------------------------------------------
                r1 = await conn.execute("delete from sales_order_line_lot where sales_order_line_id = any($1::int[])", line_ids)
                r2 = await conn.execute("delete from sales_order_line where id = any($1::int[])", line_ids)
                r3 = await conn.execute("delete from sales_order where id = any($1::int[])", ids)
                r4 = await conn.execute("delete from ledger_entry where id = any($1::int[])", [d[6] for d in DUPES.values()])
                r5 = await conn.execute("delete from stock_movement where id = any($1::int[])", [d[7] for d in DUPES.values()])
                need((r1, r2, r3, r4, r5) == ("DELETE 10",) * 5, f"delete counts: {(r1, r2, r3, r4, r5)}")
                for d in DUPES.values():
                    r = await conn.execute("update stock_lot set qty_remaining = qty_remaining + $1 where id = $2", Decimal(d[3]), d[5])
                    need(r == "UPDATE 1", "lot restore failed")

                # ---- 4. invoice 29: use the locally bought lots ------------------------------------------
                for lot_line_id, mov_id, sku, china_lot, local_lot in REPOINT:
                    need(await conn.execute("update sales_order_line_lot set stock_lot_id = $1, unit_cost_pkr = $2 where id = $3", local_lot, LOCAL_COST, lot_line_id) == "UPDATE 1", "re-point failed")
                    need(await conn.execute("update stock_movement set stock_lot_id = $1 where id = $2", local_lot, mov_id) == "UPDATE 1", "movement re-point failed")
                    need(await conn.execute("update stock_lot set qty_remaining = qty_remaining + 10 where id = $1", china_lot) == "UPDATE 1", "china lot restore failed")
                    need(await conn.execute("update stock_lot set qty_remaining = qty_remaining - 10 where id = $1 and qty_remaining >= 10", local_lot) == "UPDATE 1", "local lot consume failed")

                # ---- 5. verify ---------------------------------------------------------------------------
                n_orders = await conn.fetchval("select count(*) from sales_order")
                debit_after = await conn.fetchval("select sum(debit) from ledger_entry where account = 'Accounts Receivable'")
                party_after = {r["name"]: r["d"] for r in await conn.fetch("select p.name, sum(l.debit) d from party p join ledger_entry l on l.party_id = p.id where l.account = 'Accounts Receivable' and p.name = any($1::text[]) group by 1", list(EXPECT_PARTY_DEBIT_AFTER))}
                need(n_orders == EXPECT_REMAINING_ORDERS, f"{n_orders} sales orders left")
                need(debit_after == EXPECT_AR_DEBITS_AFTER, f"AR debits after {debit_after}")
                need(party_after == EXPECT_PARTY_DEBIT_AFTER, f"party balances after {party_after}")
                mismatch_after = [r["id"] for r in await lot_mismatches(conn)]
                need(mismatch_after == mismatch_before, f"stock-lot consistency changed: {mismatch_before} -> {mismatch_after}")
                lots = {r["id"]: r["qty_remaining"] for r in await conn.fetch("select id, qty_remaining from stock_lot where id = any($1::int[])", [630, 628, 1070, 1074, 992, 1038, 1071, 1072, 1073, 1075, 1076, 1077])}
                need(lots[630] == 82 and lots[628] == 10 and lots[1070] == 0 and lots[1074] == 0, f"lot quantities off: {lots}")
                need(all(lots[i] == (5 if i in (992, 1071, 1075) else 40 if i == 1038 else 10) for i in (992, 1038, 1071, 1072, 1073, 1075, 1076, 1077)), f"local lots off: {lots}")
                print(f"verified | sales orders {n_orders} | AR debits {debit_after} | Shoaib {party_after['Shoaib Mobile, Jhang']} | Dream {party_after['DREAM MOB SARGODAH']}")
                print("lots now:", {k: str(v) for k, v in sorted(lots.items())})
                if not APPLY:
                    raise Abort("dry run - rolling back")
        except Abort as exc:
            if "dry run" not in str(exc):
                print("ABORTED, nothing written:", exc)
                sys.exit(1)
            print("(dry run rolled back - nothing written)")
    finally:
        await conn.close()


asyncio.run(main())
