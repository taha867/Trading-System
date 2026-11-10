"""Clear invoice numbers that were carried down onto the wrong suppliers' purchase orders.

A blank "Invoice #" cell on the Local Purchase sheet was read as "same as the row above", so S&A's invoice numbers
(488, 506, 518, 532, 541) landed on AlNafeh, AMT, Javed, NS Traders and Galaxy Mobile orders that have none. These 21
purchase orders (13 from the October import, 8 from the Stage 3 import) had the wrong number; it is cleared. Only
purchase_order.invoice_number changes (their amounts are asserted unchanged).

    PROD_DSN=postgresql://… python backend/scripts/oneoff/2026_11_04_clear_carried_down_po_invoices.py [--apply]
"""
import asyncio
import os
import sys

import asyncpg

APPLY = "--apply" in sys.argv
# purchase_order id -> the wrong invoice number it carried
EXPECTED = {
    36: "488", 37: "488", 38: "488", 39: "488", 40: "488", 45: "506", 47: "518", 49: "532", 51: "541", 52: "541",
    53: "541", 54: "541", 55: "541", 104: "506", 105: "506", 106: "506", 107: "506", 108: "506", 120: "532",
    121: "532", 122: "532",
}
LINES_TOTAL = (
    "select coalesce(sum(l.qty * l.rate_pkr), 0) from purchase_order po "
    "join purchase_order_line l on l.purchase_order_id = po.id where po.id = any($1::int[])"
)


async def main() -> None:
    conn = await asyncpg.connect(os.environ["PROD_DSN"].split("?")[0], ssl=True, timeout=30)
    try:
        before_total = await conn.fetchval(LINES_TOTAL, list(EXPECTED))
        try:
            async with conn.transaction():
                rows = await conn.fetch(
                    "select po.id, po.invoice_number, po.source from purchase_order po where po.id = any($1::int[]) order by po.id",
                    list(EXPECTED),
                )
                assert len(rows) == 21 and all(r["invoice_number"] == EXPECTED[r["id"]] and r["source"] == "local" for r in rows), rows
                print("mode:", "APPLY" if APPLY else "DRY RUN (rolled back)", "| 21 purchase orders carry exactly the expected invoice numbers")
                if APPLY:
                    result = await conn.execute(
                        "update purchase_order set invoice_number = NULL where id = any($1::int[]) and invoice_number = any($2::text[])",
                        list(EXPECTED), sorted(set(EXPECTED.values())),
                    )
                    assert result == "UPDATE 21", result
                    print("updated:", result)
                assert await conn.fetchval(LINES_TOTAL, list(EXPECTED)) == before_total
                if not APPLY:
                    raise asyncpg.exceptions.PostgresError("dry run - rolling back")
        except asyncpg.exceptions.PostgresError as exc:
            if "dry run" not in str(exc):
                raise
            print("(dry run rolled back - nothing written)")
    finally:
        await conn.close()


asyncio.run(main())
