"""Make every record dated 3 September 2026 "shown only" (reference only; it affects nothing).

The owner's rule: the 3 Sept 2026 day-book entries (credit sales, local purchases, expenses and the customer payments
of that day) were bought-and-resold / carried entries. They stay visible on the screens but must not be in any balance,
cash/bank figure, stock or profit report.

In ONE transaction (default is a dry run that rolls back; --apply writes):
  0. adds the `shown_only` column to the six tables (same as migration e3b91c5d7a28) and stamps alembic_version;
  1. asserts the exact starting state (record counts, ledger rows, amounts, stock lots untouched);
  2. backs up every ledger row it deletes (and the party / account balances before) to
     backups/2026_11_12_sep3_shown_only.json (apply mode);
  3. flags the sales / purchase orders, the "no stock / no model" entries, the expenses and the payments of 3 Sept
     as shown_only, detaches the entries from their ledger rows and deletes the 34 ledger rows dated 3 Sept;
  4. verifies: no ledger row left for that date, AR / AP / cash totals moved by exactly the deleted rows, stock lots
     and stock movements unchanged, nothing outside 3 Sept touched.

    PROD_DSN=postgresql://... python backend/scripts/oneoff/2026_11_12_mark_sep3_shown_only.py [--apply]
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
DAY = date(2026, 9, 3)
BACKUP = Path(__file__).parent / "backups" / "2026_11_12_sep3_shown_only.json"
TABLES = ("sales_order", "sales_log_exception", "purchase_order", "purchase_log_exception", "expense", "payment_transaction")
DATE_COL = {
    "sales_order": "order_date", "sales_log_exception": "entry_date", "purchase_order": "order_date",
    "purchase_log_exception": "entry_date", "expense": "expense_date", "payment_transaction": "transaction_date",
}
EXPECT_ROWS = {"sales_order": 1, "sales_log_exception": 3, "purchase_order": 2, "purchase_log_exception": 10, "expense": 4, "payment_transaction": 12}
EXPECT_LEDGER_ROWS = 34
OLD_REV, NEW_REV = "d7a2e94b1c60", "e3b91c5d7a28"


class Abort(Exception):
    pass


def need(cond, msg):
    if not cond:
        raise Abort(msg)


async def snapshot(conn):
    """Totals that must move by exactly the deleted ledger rows, and totals that must not move at all."""
    ledger = await conn.fetch("select account, sum(debit) d, sum(credit) c from ledger_entry group by account order by account")
    parties = await conn.fetch("select p.name, sum(l.debit - l.credit) bal from ledger_entry l join party p on p.id = l.party_id group by p.name order by p.name")
    accounts = await conn.fetch("select payment_account_id, sum(debit - credit) bal from ledger_entry where payment_account_id is not null group by 1 order by 1")
    stock = await conn.fetchrow("select count(*) n, sum(qty_remaining) q, sum(qty_remaining * landed_cost_pkr) v from stock_lot")
    moves = await conn.fetchrow("select count(*) n, sum(qty_delta) q from stock_movement")
    return {
        "ledger": {r["account"]: (r["d"], r["c"]) for r in ledger},
        "parties": {r["name"]: r["bal"] for r in parties},
        "accounts": {r["payment_account_id"]: r["bal"] for r in accounts},
        "stock": tuple(stock.values()),
        "moves": tuple(moves.values()),
    }


async def main():
    conn = await asyncpg.connect(os.environ["PROD_DSN"].split("?")[0], ssl=True, timeout=30)
    tx = conn.transaction()
    await tx.start()
    try:
        # ---- 0. schema (transactional DDL: rolled back in a dry run)
        rev = await conn.fetchval("select version_num from alembic_version")
        need(rev in (OLD_REV, NEW_REV), f"unexpected alembic revision {rev}")
        for t in TABLES:
            await conn.execute(f"alter table {t} add column if not exists shown_only boolean not null default false")
        await conn.execute("update alembic_version set version_num = $1", NEW_REV)

        # ---- 1. preconditions
        for t in TABLES:
            n = await conn.fetchval(f"select count(*) from {t} where {DATE_COL[t]} = $1", DAY)
            need(n == EXPECT_ROWS[t], f"{t}: expected {EXPECT_ROWS[t]} rows on {DAY}, found {n}")
            need(await conn.fetchval(f"select count(*) from {t} where shown_only") == 0, f"{t}: already has shown-only rows")
        ledger = await conn.fetch("select * from ledger_entry where entry_date = $1 order by id", DAY)
        need(len(ledger) == EXPECT_LEDGER_ROWS, f"expected {EXPECT_LEDGER_ROWS} ledger rows on {DAY}, found {len(ledger)}")
        refs = {r["reference_type"] for r in ledger}
        need(refs <= {"sales_order", "sales_log_exception", "purchase_order", "local_purchase_exception", "payment_transaction"}, f"unexpected ledger reference types {refs}")
        before = await snapshot(conn)

        # ---- 2. backup
        if APPLY:
            BACKUP.parent.mkdir(exist_ok=True)
            backup = {"day": str(DAY), "ledger_entries_deleted": [{k: str(v) for k, v in dict(r).items()} for r in ledger],
                      "party_balances_before": {k: str(v) for k, v in before["parties"].items()},
                      "account_balances_before": {str(k): str(v) for k, v in before["accounts"].items()}}
            for t in ("sales_log_exception", "purchase_log_exception"):
                backup[f"{t}_ledger_links"] = {str(r["id"]): r["ledger_entry_id"] for r in await conn.fetch(f"select id, ledger_entry_id from {t} where entry_date = $1", DAY)}
            BACKUP.write_text(json.dumps(backup, indent=1))

        # ---- 3. flag, detach, delete
        for t in TABLES:
            await conn.execute(f"update {t} set shown_only = true where {DATE_COL[t]} = $1", DAY)
        for t in ("sales_log_exception", "purchase_log_exception"):
            await conn.execute(f"update {t} set ledger_entry_id = null where entry_date = $1", DAY)
        deleted = await conn.execute("delete from ledger_entry where entry_date = $1", DAY)
        need(deleted == f"DELETE {EXPECT_LEDGER_ROWS}", f"deleted {deleted}")

        # ---- 4. verify
        after = await snapshot(conn)
        need(await conn.fetchval("select count(*) from ledger_entry where entry_date = $1", DAY) == 0, "ledger rows remain")
        need(before["stock"] == after["stock"], "stock lots changed")
        need(before["moves"] == after["moves"], "stock movements changed")
        d_deb = sum(r["debit"] for r in ledger); d_cred = sum(r["credit"] for r in ledger)
        b_deb = sum(v[0] for v in before["ledger"].values()); b_cred = sum(v[1] for v in before["ledger"].values())
        a_deb = sum(v[0] for v in after["ledger"].values()); a_cred = sum(v[1] for v in after["ledger"].values())
        need(b_deb - a_deb == d_deb and b_cred - a_cred == d_cred, "ledger totals moved by the wrong amount")
        for t in TABLES:
            n = await conn.fetchval(f"select count(*) from {t} where shown_only")
            need(n == EXPECT_ROWS[t], f"{t}: {n} shown-only rows after")

        print(f"{'APPLY' if APPLY else 'DRY RUN'}: flagged {sum(EXPECT_ROWS.values())} records on {DAY}, deleted {EXPECT_LEDGER_ROWS} ledger rows"
              f" (debits {d_deb}, credits {d_cred}); stock lots and movements unchanged")
        print("Account totals (debit, credit) before -> after:")
        for acct in sorted(before["ledger"]):
            print(f"  {acct:32s} {before['ledger'][acct]} -> {after['ledger'].get(acct)}")
        print("Customer / supplier balances that change (debit-credit; + = they owe us, - = we owe them):")
        for name in sorted(set(before["parties"]) | set(after["parties"])):
            b, a = before["parties"].get(name, Decimal(0)), after["parties"].get(name, Decimal(0))
            if b != a:
                print(f"  {name:40s} {b:>14} -> {a:>14}  ({a - b:+})")
        print("Cash / bank accounts that change:")
        for k in sorted(set(before["accounts"]) | set(after["accounts"])):
            b, a = before["accounts"].get(k, Decimal(0)), after["accounts"].get(k, Decimal(0))
            if b != a:
                print(f"  payment_account {k}: {b} -> {a}  ({a - b:+})")
        if APPLY:
            await tx.commit()
            print("committed")
        else:
            await tx.rollback()
            print("rolled back (dry run) - nothing was changed")
    except Abort as e:
        await tx.rollback()
        print(f"ABORTED, nothing written: {e}")
        sys.exit(1)
    except BaseException:
        await tx.rollback()
        raise
    finally:
        await conn.close()


asyncio.run(main())
