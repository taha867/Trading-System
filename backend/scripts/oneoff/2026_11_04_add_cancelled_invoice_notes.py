"""Give the 8 cancelled September 2026 invoices a note saying so (they had none).

Cancelled invoices live in sales_log_exception (kind "cancelled_invoice", amount 0, no ledger entry) because they
have no items and can't be sales orders. Only the `note` column of those 8 rows changes.

    PROD_DSN=postgresql://… python backend/scripts/oneoff/2026_11_04_add_cancelled_invoice_notes.py [--apply]
"""
import asyncio
import os
import sys

import asyncpg

APPLY = "--apply" in sys.argv
# (sales_log_exception id, invoice number, sheet row in "Daily Cash Book (Sept 2026).xlsx" > Credit Sale)
TARGETS = [(1, "1", 5), (2, "2", 6), (19, "10", 66), (20, "12", 92), (21, "15", 104), (23, "22", 233), (25, "28", 288), (26, "30", 351)]


def note_for(sheet_row: int) -> str:
    return f"Cancelled invoice - per Sept 2026 day book (Credit Sale sheet row {sheet_row})"


async def main() -> None:
    conn = await asyncpg.connect(os.environ["PROD_DSN"].split("?")[0], ssl=True, timeout=30)
    try:
        async with conn.transaction():
            print("mode:", "APPLY" if APPLY else "DRY RUN (rolled back)")
            changed = 0
            for ex_id, invoice, sheet_row in TARGETS:
                before = await conn.fetchrow(
                    "select id, kind, invoice_number, note, amount_pkr, ledger_entry_id from sales_log_exception where id=$1", ex_id
                )
                assert before and before["kind"] == "cancelled_invoice" and before["invoice_number"] == invoice
                assert before["amount_pkr"] == 0 and before["ledger_entry_id"] is None, before
                if before["note"] is not None:
                    print(f"  id={ex_id} inv={invoice}: already has a note -> left untouched")
                    continue
                print(f"  id={ex_id} inv={invoice}: note NULL -> {note_for(sheet_row)!r}")
                if APPLY:
                    result = await conn.execute(
                        "update sales_log_exception set note=$1 where id=$2 and kind='cancelled_invoice' and note is null",
                        note_for(sheet_row), ex_id,
                    )
                    assert result == "UPDATE 1", result
                changed += 1
            print("rows changed:" if APPLY else "rows that would change:", changed)
            if not APPLY:
                raise asyncpg.exceptions.PostgresError("dry run - rolling back")
    except asyncpg.exceptions.PostgresError as exc:
        if "dry run" not in str(exc):
            raise
        print("(dry run rolled back - nothing written)")
    finally:
        await conn.close()


asyncio.run(main())
