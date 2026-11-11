"""Move local purchase invoice 453 (S&A, 88 pcs @ Rs 98 = Rs 8,624) from 3 Sept to 4 Sept 2026 and match it to credit sale invoice 5.

The owner's decision: the 453 purchase on the Local Purchase tab belongs to credit sale invoice 5 (S&A, 4 Sept: order #8
Rs 4,704 + five "no stock" lines Rs 3,920 = Rs 8,624). It is therefore a normal 4 Sept entry, not a "3 Sept shown-only" one.

In ONE transaction (default is a dry run that rolls back; --apply writes):
  1. asserts the starting state (the entry, its shown-only flag, no ledger row) and that the sale side adds up to the
     same Rs 8,624 on 4 Sept;
  2. backs up the old values to backups/2026_11_12_purchase_453_to_sep4.json (apply mode);
  3. sets purchase_log_exception 27 to 2026-09-04, shown_only = false, adds a note, and re-creates its Accounts Payable
     ledger row (credit Rs 8,624, S&A, dated 4 Sept) that the 3 Sept "shown only" change had removed;
  4. verifies Accounts Payable credits went up by exactly Rs 8,624, S&A's balance by -8,624, nothing else moved.

    PROD_DSN=postgresql://... python backend/scripts/oneoff/2026_11_12_move_purchase_453_to_sep4.py [--apply]
"""
import asyncio
import json
import os
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import asyncpg

APPLY = "--apply" in sys.argv
BACKUP = Path(__file__).parent / "backups" / "2026_11_12_purchase_453_to_sep4.json"
ENTRY_ID, NEW_DATE, AMOUNT = 27, date(2026, 9, 4), Decimal("8624.00")
NOTE = "Matches credit sale invoice 5 (S&A, 4 Sept 2026): 88 pcs @ 98"


class Abort(Exception):
    pass


def need(cond, msg):
    if not cond:
        raise Abort(msg)


async def main():
    conn = await asyncpg.connect(os.environ["PROD_DSN"].split("?")[0], ssl=True, timeout=30)
    tx = conn.transaction()
    await tx.start()
    try:
        e = await conn.fetchrow("select * from purchase_log_exception where id = $1", ENTRY_ID)
        need(e and e["invoice_number"] == "453" and e["amount_pkr"] == AMOUNT and e["entry_date"] == date(2026, 9, 3) and e["shown_only"] and e["ledger_entry_id"] is None, "entry 27 is not in the expected state")
        sa = await conn.fetchval("select id from party where name = 'S&A'")
        need(e["party_id"] == sa, "entry 27 is not S&A's")
        sale_orders = await conn.fetchval("select coalesce(sum(round(l.qty * l.rate_pkr, 2)), 0) from sales_order so join sales_order_line l on l.sales_order_id = so.id where so.invoice_number = '5' and so.party_id = $1 and so.order_date = $2", sa, NEW_DATE)
        sale_entries = await conn.fetchval("select coalesce(sum(amount_pkr), 0) from sales_log_exception where invoice_number = '5' and party_id = $1 and entry_date = $2", sa, NEW_DATE)
        need(sale_orders + sale_entries == AMOUNT, f"credit sale invoice 5 on 4 Sept is {sale_orders + sale_entries}, not {AMOUNT}")
        before = {
            "ap": tuple(await conn.fetchrow("select sum(debit), sum(credit) from ledger_entry where account = 'Accounts Payable'")),
            "sa": await conn.fetchval("select sum(debit - credit) from ledger_entry where party_id = $1", sa),
            "all": tuple(await conn.fetchrow("select count(*), sum(debit), sum(credit) from ledger_entry")),
        }
        if APPLY:
            BACKUP.parent.mkdir(exist_ok=True)
            BACKUP.write_text(json.dumps({k: str(v) for k, v in dict(e).items()}, indent=1))
        ledger_id = await conn.fetchval(
            "insert into ledger_entry (entry_date, account, debit, credit, reference_type, reference_id, party_id) values ($1, 'Accounts Payable', 0, $2, 'local_purchase_exception', 13, $3) returning id",
            NEW_DATE, AMOUNT, sa)
        note = (e["note"] + " | " if e["note"] else "") + NOTE
        await conn.execute("update purchase_log_exception set entry_date = $1, shown_only = false, note = $2, ledger_entry_id = $3 where id = $4", NEW_DATE, note, ledger_id, ENTRY_ID)
        after = {
            "ap": tuple(await conn.fetchrow("select sum(debit), sum(credit) from ledger_entry where account = 'Accounts Payable'")),
            "sa": await conn.fetchval("select sum(debit - credit) from ledger_entry where party_id = $1", sa),
            "all": tuple(await conn.fetchrow("select count(*), sum(debit), sum(credit) from ledger_entry")),
        }
        need(after["ap"][1] - before["ap"][1] == AMOUNT and after["ap"][0] == before["ap"][0], "Accounts Payable moved by the wrong amount")
        need(after["sa"] - before["sa"] == -AMOUNT, "S&A balance moved by the wrong amount")
        need(after["all"][0] - before["all"][0] == 1 and after["all"][2] - before["all"][2] == AMOUNT and after["all"][1] == before["all"][1], "ledger totals moved by the wrong amount")
        print(f"{'APPLY' if APPLY else 'DRY RUN'}: invoice 453 moved to {NEW_DATE}, matched to credit sale invoice 5; S&A balance {before['sa']} -> {after['sa']} ({after['sa'] - before['sa']:+}); Accounts Payable credits +{AMOUNT}")
        if APPLY:
            await tx.commit(); print("committed")
        else:
            await tx.rollback(); print("rolled back (dry run) - nothing was changed")
    except Abort as exc:
        await tx.rollback(); print(f"ABORTED, nothing written: {exc}"); sys.exit(1)
    except BaseException:
        await tx.rollback(); raise
    finally:
        await conn.close()


asyncio.run(main())
