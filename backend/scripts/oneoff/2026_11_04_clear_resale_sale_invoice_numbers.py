"""Clear the supplier invoice numbers that were copied onto 10 same-day resale sales.

The Local Purchase sheet's "Invoice #" is the SUPPLIER's invoice for a purchase. The import copied it onto the sale that
resells those goods, so 9 sales to Shoaib Mobile, Jhang showed "541" (S&A's invoice) and one Dream Mobile resale showed
"5" (colliding with an unrelated S&A sale). The sheet gives these resales no invoice number of their own, so it is cleared.
Only sales_order.invoice_number changes: amounts, stock, ledger and balances are untouched. The purchase orders keep the
supplier's number, which is correct on the purchase side.

    PROD_DSN=postgresql://… python backend/scripts/oneoff/2026_11_04_clear_resale_sale_invoice_numbers.py [--apply]
"""
import asyncio
import os
import sys

import asyncpg

APPLY = "--apply" in sys.argv
SHOAIB_SALES = [26] + list(range(45, 53))  # all carried invoice "541", party "Shoaib Mobile, Jhang", dated 2026-09-25


async def main() -> None:
    conn = await asyncpg.connect(os.environ["PROD_DSN"].split("?")[0], ssl=True, timeout=30)
    try:
        try:
            async with conn.transaction():
                rows_541 = await conn.fetch(
                    "select so.id, so.order_date, p.name from sales_order so join party p on p.id = so.party_id "
                    "where so.invoice_number = '541' order by so.id"
                )
                assert [r["id"] for r in rows_541] == SHOAIB_SALES, [r["id"] for r in rows_541]
                assert all(r["name"] == "Shoaib Mobile, Jhang" and str(r["order_date"]) == "2026-09-25" for r in rows_541)
                dream = await conn.fetch(
                    "select so.id from sales_order so join party p on p.id = so.party_id "
                    "where so.invoice_number = '5' and p.name like 'DREAM MOB%'"
                )
                assert len(dream) == 1, f"expected exactly one Dream Mobile sale with invoice 5, found {len(dream)}"
                targets = SHOAIB_SALES + [dream[0]["id"]]
                before = {
                    sid: await conn.fetchval("select coalesce(sum(qty * rate_pkr), 0) from sales_order_line where sales_order_id = $1", sid)
                    for sid in targets
                }
                print("mode:", "APPLY" if APPLY else "DRY RUN (rolled back)", "| sales to clear:", targets)
                if APPLY:
                    result = await conn.execute(
                        "update sales_order set invoice_number = NULL where id = any($1::int[]) and invoice_number in ('541', '5')", targets
                    )
                    assert result == "UPDATE 10", result
                    print("updated:", result)
                for sid, total in before.items():  # nothing but the invoice number may have changed
                    assert await conn.fetchval("select coalesce(sum(qty * rate_pkr), 0) from sales_order_line where sales_order_id = $1", sid) == total
                if not APPLY:
                    raise asyncpg.exceptions.PostgresError("dry run - rolling back")
        except asyncpg.exceptions.PostgresError as exc:
            if "dry run" not in str(exc):
                raise
            print("(dry run rolled back - nothing written)")
    finally:
        await conn.close()


asyncio.run(main())
