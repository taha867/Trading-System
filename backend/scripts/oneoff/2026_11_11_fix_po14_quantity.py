"""Correct purchase order #14 (Mohsin, 8 Sep 2026) and stock lot 562: one quantity typo, three stale numbers.

The order was first entered with 517 iPhone 14 Pro Max Simple Privacy Protectors and later corrected to 47. The lot, its
Inventory ledger row and the order's lines were fixed, but the two Accounts Payable ledger rows and the lot's receipt
movement kept the old 517 (470 pcs x Rs 71.66 = Rs 33,680.20). Mohsin_Stock_Sent_Comparison.xlsx confirms 47: 1,965
Simple Privacy pieces received = Rs 140,811.90 = the 17 lines of this order.

Changes (rows 585 and 603 are the import's payable + equal offsetting debit, so Mohsin's net balance does not change):
  ledger_entry 585 credit 174,492.10 -> 140,811.90
  ledger_entry 603 debit  174,492.10 -> 140,811.90
  stock_movement 562 qty_delta 517   -> 47

    PROD_DSN=postgresql://... python backend/scripts/oneoff/2026_11_11_fix_po14_quantity.py [--apply]
"""
import asyncio
import json
import os
import sys
from decimal import Decimal
from pathlib import Path

import asyncpg

APPLY = "--apply" in sys.argv
BACKUP = Path(__file__).parent / "backups" / "2026_11_11_po14_fix.json"
OLD, NEW = Decimal("174492.10"), Decimal("140811.90")


class Abort(Exception):
    pass


def need(cond, msg):
    if not cond:
        raise Abort(msg)


async def snapshot(conn):
    return {
        "po_vs_ledger": [tuple(r) for r in await conn.fetch(
            "select po.id from purchase_order po join (select reference_id id, sum(credit) cr from ledger_entry "
            "where reference_type='purchase_order' and account='Accounts Payable' group by 1) led on led.id=po.id "
            "join (select purchase_order_id id, sum(round(qty*rate_pkr,2)) t from purchase_order_line group by 1) ln on ln.id=po.id "
            "where led.cr <> ln.t order by 1")],
        "receipt_mismatch": [tuple(r) for r in await conn.fetch(
            "select sl.id from stock_lot sl join stock_movement m on m.stock_lot_id=sl.id and m.movement_type='receipt' "
            "where sl.qty_received <> m.qty_delta order by 1")],
        "lot_mismatch": [tuple(r) for r in await conn.fetch(
            "select sl.id from stock_lot sl left join stock_movement m on m.stock_lot_id=sl.id "
            "group by sl.id having sl.qty_remaining <> coalesce(sum(m.qty_delta),0) order by 1")],
        "mohsin_ap_net": await conn.fetchval("select sum(credit)-sum(debit) from ledger_entry where account='Accounts Payable' and party_id=1"),
        "inventory_total": await conn.fetchval("select sum(debit)-sum(credit) from ledger_entry where account='Inventory'"),
    }


async def main() -> None:
    conn = await asyncpg.connect(os.environ["PROD_DSN"].split("?")[0], ssl=True, timeout=30)
    try:
        try:
            async with conn.transaction():
                print("mode:", "APPLY" if APPLY else "DRY RUN (rolled back)")
                po = await conn.fetchrow("select po.id, po.party_id, p.name from purchase_order po join party p on p.id=po.party_id where po.id=14")
                need(po and po["name"] == "Mohsin", f"PO 14 is not Mohsin's: {dict(po) if po else None}")
                lines = await conn.fetchval("select sum(round(qty*rate_pkr,2)) from purchase_order_line where purchase_order_id=14")
                need(lines == NEW and await conn.fetchval("select count(*) from purchase_order_line where purchase_order_id=14") == 17, f"PO 14 lines are {lines}")
                led = await conn.fetch("select * from ledger_entry where id in (585, 603) order by id")
                need(len(led) == 2 and (led[0]["credit"], led[0]["debit"]) == (OLD, 0) and (led[1]["debit"], led[1]["credit"]) == (OLD, 0)
                     and all(l["account"] == "Accounts Payable" and l["reference_type"] == "purchase_order" and l["reference_id"] == 14 for l in led), "ledger rows 585/603 are not as expected")
                mov = await conn.fetchrow("select * from stock_movement where id=562")
                lot = await conn.fetchrow("select * from stock_lot where id=562")
                need(mov["stock_lot_id"] == 562 and mov["movement_type"] == "receipt" and mov["qty_delta"] == Decimal("517.00"), "movement 562 is not the 517 receipt")
                need(lot["qty_received"] == Decimal("47.00") and lot["qty_remaining"] == Decimal("47.00"), "lot 562 is not 47/47")
                inv = await conn.fetchval("select sum(debit) from ledger_entry where account='Inventory' and reference_type='stock_lot' and reference_id in (select id from stock_lot where purchase_order_line_id in (select id from purchase_order_line where purchase_order_id=14))")
                need(inv == NEW, f"Inventory rows for PO 14 sum to {inv}")
                before = await snapshot(conn)
                need(before["po_vs_ledger"] == [(14,)] and before["receipt_mismatch"] == [(562,)] and before["lot_mismatch"] == [(562,)], f"unexpected other mismatches: {before}")
                print("starting state OK |", {k: str(v) for k, v in before.items()})
                if APPLY:
                    BACKUP.write_text(json.dumps({"ledger_entry": [dict(l) for l in led], "stock_movement": dict(mov), "stock_lot": dict(lot)}, indent=2, default=str))
                    print("backup written:", BACKUP)
                need(await conn.execute("update ledger_entry set credit=$1 where id=585 and credit=$2", NEW, OLD) == "UPDATE 1", "585 update failed")
                need(await conn.execute("update ledger_entry set debit=$1 where id=603 and debit=$2", NEW, OLD) == "UPDATE 1", "603 update failed")
                need(await conn.execute("update stock_movement set qty_delta=47 where id=562 and qty_delta=517") == "UPDATE 1", "movement update failed")
                after = await snapshot(conn)
                need(after["po_vs_ledger"] == [] and after["receipt_mismatch"] == [] and after["lot_mismatch"] == [], f"mismatches remain: {after}")
                need(after["mohsin_ap_net"] == before["mohsin_ap_net"] and after["inventory_total"] == before["inventory_total"], "a balance changed")
                print("verified: no PO/ledger mismatch, no lot mismatch, Mohsin net payable and Inventory total unchanged")
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
