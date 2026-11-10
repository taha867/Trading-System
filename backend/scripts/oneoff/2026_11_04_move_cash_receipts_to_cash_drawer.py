"""Move the two cash-invoice receipts from "Unspecified (to be decided)" to the "Cash drawer" account.

Invoices 14 (Rs 4,200, 12 Sep) and 24 (Rs 150, 19 Sep) are cash sales to the walk-in party; the day book gives no
payment method for them, so the import parked them on the placeholder account. Changes exactly 2 payment_transaction
rows and the 2 ledger rows that mirror them (account label + payment_account_id). The customer-side ledger rows,
amounts and dates are untouched.

    PROD_DSN=postgresql://… python backend/scripts/oneoff/2026_11_04_move_cash_receipts_to_cash_drawer.py [--apply]
"""
import asyncio
import os
import sys

import asyncpg

APPLY = "--apply" in sys.argv
PAYMENTS = (165, 173)  # payment_transaction ids: Rs 4,200 and Rs 150, party "Cash (Walk-in / Anonymous)"
LEDGER = (1234, 1250)  # their account-leg ledger_entry ids
FROM_ACCOUNT, TO_ACCOUNT = 6, 4  # "Unspecified (to be decided)" -> "Cash drawer"


async def balances(conn):
    rows = await conn.fetch(
        "select a.id, a.label, coalesce(sum(l.debit - l.credit), 0) bal from payment_account a "
        "left join ledger_entry l on l.payment_account_id = a.id where a.id in ($1, $2) group by a.id, a.label",
        FROM_ACCOUNT, TO_ACCOUNT,
    )
    return {r["id"]: (r["label"], r["bal"]) for r in rows}


async def main() -> None:
    conn = await asyncpg.connect(os.environ["PROD_DSN"].split("?")[0], ssl=True, timeout=30)
    try:
        print("before:", await balances(conn))
        try:
            async with conn.transaction():
                payments = await conn.fetch(
                    "select t.id, t.amount, t.direction, t.payment_account_id, p.name from payment_transaction t "
                    "join party p on p.id = t.party_id where t.id = any($1::int[])", list(PAYMENTS),
                )
                assert len(payments) == 2 and all(
                    p["direction"] == "in" and p["payment_account_id"] == FROM_ACCOUNT and p["name"].startswith("Cash (Walk-in")
                    for p in payments
                ), payments
                assert sorted(float(p["amount"]) for p in payments) == [150.0, 4200.0], payments
                ledger = await conn.fetch(
                    "select id, account, payment_account_id, reference_type, reference_id from ledger_entry where id = any($1::int[])",
                    list(LEDGER),
                )
                assert len(ledger) == 2 and all(
                    l["payment_account_id"] == FROM_ACCOUNT and l["reference_type"] == "payment_transaction"
                    and l["reference_id"] in PAYMENTS and l["account"] == "Unspecified (to be decided)"
                    for l in ledger
                ), ledger
                print("mode:", "APPLY" if APPLY else "DRY RUN (rolled back)", "| 2 payments + 2 ledger rows match the expectation")
                if APPLY:
                    r1 = await conn.execute(
                        "update payment_transaction set payment_account_id=$1 where id = any($2::int[]) and payment_account_id=$3",
                        TO_ACCOUNT, list(PAYMENTS), FROM_ACCOUNT,
                    )
                    r2 = await conn.execute(
                        "update ledger_entry set payment_account_id=$1, account='Cash drawer' where id = any($2::int[]) and payment_account_id=$3",
                        TO_ACCOUNT, list(LEDGER), FROM_ACCOUNT,
                    )
                    assert (r1, r2) == ("UPDATE 2", "UPDATE 2"), (r1, r2)
                    print("updated:", r1, "|", r2)
                else:
                    raise asyncpg.exceptions.PostgresError("dry run - rolling back")
        except asyncpg.exceptions.PostgresError as exc:
            if "dry run" not in str(exc):
                raise
            print("(dry run rolled back - nothing written)")
        print("after: ", await balances(conn))
    finally:
        await conn.close()


asyncio.run(main())
