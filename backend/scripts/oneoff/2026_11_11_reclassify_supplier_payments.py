"""Record the day book's supplier payments as supplier payments, not expenses; keep Personal out of shop profit.

The Expenses tab of the September day book also holds payments to suppliers. Stage 1 stored every row as an expense, so
13 payments (Rs 5,005,801) were counted as shop running costs and never reduced what is owed to the supplier.

For each of the 13 payments this script (one transaction; default is a dry run that rolls back; --apply writes):
  - sets the payment transaction's party to the supplier and clears its "expense" reference;
  - posts the Accounts Payable debit for that party, exactly as payments.service.create_payment_transaction does;
  - deletes the expense row.
The payment-account leg of each payment is untouched, so cash and bank balances do not change.
It also creates the party "Shoaib Traders / Sunny Glass (Import)" (china_vendor) for the Rs 4,338,130 of import
payments (recorded as an advance, no purchase against them), and marks the Personal expense category as not counting
toward shop profit (needs migration d7a2e94b1c60).

    PROD_DSN=postgresql://... python backend/scripts/oneoff/2026_11_11_reclassify_supplier_payments.py [--apply]
"""
import asyncio
import json
import os
import sys
from decimal import Decimal
from pathlib import Path

import asyncpg

APPLY = "--apply" in sys.argv
BACKUP = Path(__file__).parent / "backups" / "2026_11_11_reclassify_supplier_payments.json"
IMPORT_PARTY = "Shoaib Traders / Sunny Glass (Import)"
PERSONAL_CATEGORY_ID, SHOP_CATEGORY_ID = 4, 5

# expense id -> (payment_transaction id, party id or IMPORT_PARTY, date, amount, description)
PAYMENTS = {
    58: (59, 32, "2026-09-10", 175000, "S&A"),
    57: (58, 33, "2026-09-10", 15300, "Al NAfeh traders "),
    117: (118, 33, "2026-09-23", 33520, "Al nafeh traders (BOP)"),
    125: (126, 33, "2026-09-26", 5100, "Alnafah Traders(UBL to easypesa)"),
    43: (44, 38, "2026-09-07", 1500, "A. Power payment mazafar garh (Cash PAid)"),
    119: (120, 36, "2026-09-24", 222500, "Galaxy Mobile Kamran (OG =  4000)"),
    72: (73, 34, "2026-09-14", 9251, "Javeed traders"),
    112: (113, 35, "2026-09-22", 205500, "NS traders (from FBL)"),
    81: (82, IMPORT_PARTY, "2026-09-16", 1000000, "RMB to shoaib "),
    82: (83, IMPORT_PARTY, "2026-09-16", 1000000, "shoaib traders pottery "),
    85: (86, IMPORT_PARTY, "2026-09-17", 147000, "Sunny Glass"),
    118: (119, IMPORT_PARTY, "2026-09-23", 2153065, "Sunny GLass(RMB=50048*43.02)"),
    120: (121, IMPORT_PARTY, "2026-09-24", 38065, "Shoaib (RMB BAlance OG)"),
}
EXPECTED_PARTY_NAMES = {32: "S&A", 33: "AlNafeh Traders", 34: "Javed Traders", 35: "NS Traders", 36: "Galaxy Mobile, Kamran", 38: "A.Power Traders"}
TOTAL = Decimal("5005801")
# September payable per supplier after the change (credits - debits); matches the workbook's Supplier Ledger tab.
EXPECT_NET_AFTER = {32: Decimal("126635"), 33: Decimal("51250"), 34: Decimal("-1"), 35: Decimal("-500"), 36: Decimal("0"), 38: Decimal("0")}


class Abort(Exception):
    pass


def need(cond, msg):
    if not cond:
        raise Abort(msg)


async def totals(conn):
    return {
        "payments_out": [tuple(r) for r in await conn.fetch("select count(*), sum(amount) from payment_transaction where direction='out'")],
        "account_ledger": [tuple(r) for r in await conn.fetch("select payment_account_id, sum(debit), sum(credit) from ledger_entry where payment_account_id is not null group by 1 order by 1")],
        "ar": [tuple(r) for r in await conn.fetch("select sum(debit), sum(credit) from ledger_entry where account='Accounts Receivable'")],
        "inventory": [tuple(r) for r in await conn.fetch("select sum(debit), sum(credit) from ledger_entry where account='Inventory'")],
        "mohsin_net": await conn.fetchval("select sum(credit)-sum(debit) from ledger_entry where account='Accounts Payable' and party_id=1"),
    }


async def main() -> None:
    conn = await asyncpg.connect(os.environ["PROD_DSN"].split("?")[0], ssl=True, timeout=30)
    try:
        try:
            async with conn.transaction():
                print("mode:", "APPLY" if APPLY else "DRY RUN (rolled back)")
                # ---- 1. starting state ----------------------------------------------------------------
                need(await conn.fetchval("select count(*) from information_schema.columns where table_name='expense_category' and column_name='counts_toward_profit'") == 1,
                     "expense_category.counts_toward_profit is missing - apply migration d7a2e94b1c60 first")
                need(await conn.fetchval("select count(*) from party where name = $1", IMPORT_PARTY) == 0, "the import party already exists")
                for pid, name in EXPECTED_PARTY_NAMES.items():
                    row = await conn.fetchrow("select name, roles, is_active from party where id=$1", pid)
                    need(row and row["name"] == name and "local_vendor" in row["roles"] and row["is_active"], f"party {pid} is not {name}")
                exp_ids = list(PAYMENTS)
                expenses = {r["id"]: r for r in await conn.fetch("select * from expense where id = any($1::int[])", exp_ids)}
                need(len(expenses) == 13, f"found {len(expenses)} of 13 expenses")
                pts = {r["id"]: r for r in await conn.fetch("select * from payment_transaction where id = any($1::int[])", [v[0] for v in PAYMENTS.values()])}
                need(len(pts) == 13, "payment transactions missing")
                legs = {}
                for e_id, (pt_id, party, d, amt, desc) in PAYMENTS.items():
                    e, pt = expenses[e_id], pts[pt_id]
                    need((str(e["expense_date"]), e["amount"], e["description"], e["category_id"], e["status"]) == (d, Decimal(amt), desc, SHOP_CATEGORY_ID, "confirmed"), f"expense {e_id} differs: {dict(e)}")
                    need((pt["direction"], pt["amount"], pt["party_id"], pt["reference_type"], pt["reference_id"], str(pt["transaction_date"])) == ("out", Decimal(amt), None, "expense", e_id, d), f"payment {pt_id} differs: {dict(pt)}")
                    leg = await conn.fetch("select * from ledger_entry where reference_type='payment_transaction' and reference_id=$1", pt_id)
                    need(len(leg) == 1 and leg[0]["credit"] == Decimal(amt) and leg[0]["debit"] == 0 and leg[0]["party_id"] is None, f"ledger rows of payment {pt_id} differ")
                    legs[pt_id] = leg[0]
                need(sum(Decimal(v[3]) for v in PAYMENTS.values()) == TOTAL, "payments do not add up to 5,005,801")
                cat = await conn.fetchrow("select name, counts_toward_profit from expense_category where id=$1", PERSONAL_CATEGORY_ID)
                need(cat["name"] == "Personal" and cat["counts_toward_profit"] is True, "Personal category is not as expected")
                before = await totals(conn)
                exp_before = await conn.fetchrow("select count(*) n, sum(amount) s from expense")
                need((exp_before["n"], exp_before["s"]) == (131, Decimal("6352404")), f"expense table is {dict(exp_before)}")
                print("starting state OK")

                if APPLY:
                    BACKUP.write_text(json.dumps({
                        "expense": [dict(expenses[i]) for i in exp_ids], "payment_transaction": [dict(pts[v[0]]) for v in PAYMENTS.values()],
                        "ledger_entry": [dict(legs[v[0]]) for v in PAYMENTS.values()],
                    }, indent=2, default=str))
                    print("backup written:", BACKUP)

                # ---- 2. the import party -----------------------------------------------------------------
                import_id = await conn.fetchval(
                    "insert into party (name, roles, opening_balance, is_active) values ($1, $2, 0, true) returning id", IMPORT_PARTY, ["china_vendor"])

                # ---- 3. convert the 13 payments ----------------------------------------------------------
                for e_id, (pt_id, party, d, amt, desc) in PAYMENTS.items():
                    pid = import_id if party == IMPORT_PARTY else party
                    r = await conn.execute("update payment_transaction set party_id=$1, reference_type=NULL, reference_id=NULL where id=$2 and reference_type='expense' and reference_id=$3", pid, pt_id, e_id)
                    need(r == "UPDATE 1", f"payment {pt_id} update failed")
                    await conn.execute(
                        "insert into ledger_entry (entry_date, account, debit, credit, party_id, reference_type, reference_id) values ($1, 'Accounts Payable', $2, 0, $3, 'payment_transaction', $4)",
                        legs[pt_id]["entry_date"], Decimal(amt), pid, pt_id)
                    need(await conn.execute("delete from expense where id=$1", e_id) == "DELETE 1", f"expense {e_id} delete failed")

                # ---- 4. Personal does not count toward shop profit ---------------------------------------
                need(await conn.execute("update expense_category set counts_toward_profit=false where id=$1 and name='Personal'", PERSONAL_CATEGORY_ID) == "UPDATE 1", "category update failed")

                # ---- 5. verify ---------------------------------------------------------------------------
                after = await totals(conn)
                need(all(after[k] == before[k] for k in before), "a payment-account, receivable, inventory or Mohsin total changed")
                ap = await conn.fetchrow("select count(*) n, sum(debit) s from ledger_entry where account='Accounts Payable' and reference_type='payment_transaction' and reference_id = any($1::int[])", [v[0] for v in PAYMENTS.values()])
                need((ap["n"], ap["s"]) == (13, TOTAL), f"AP debits {dict(ap)}")
                exp_after = await conn.fetchrow("select count(*) n, sum(amount) s from expense")
                need((exp_after["n"], exp_after["s"]) == (118, Decimal("1346603")), f"expenses after: {dict(exp_after)}")
                cats = {r["id"]: r["s"] for r in await conn.fetch("select category_id id, sum(amount) s from expense group by 1")}
                need(cats == {SHOP_CATEGORY_ID: Decimal("184844"), PERSONAL_CATEGORY_ID: Decimal("1161759")}, f"category totals {cats}")
                for pid, want in EXPECT_NET_AFTER.items():
                    net = await conn.fetchval("select coalesce(sum(credit)-sum(debit),0) from ledger_entry where account='Accounts Payable' and party_id=$1 and entry_date between '2026-09-01' and '2026-09-30'", pid)
                    need(net == want, f"party {pid} September payable is {net}, expected {want}")
                adv = await conn.fetchval("select sum(debit)-sum(credit) from ledger_entry where account='Accounts Payable' and party_id=$1", import_id)
                need(adv == Decimal("4338130"), f"import advance is {adv}")
                print("verified: 13 AP debits Rs", TOTAL, "| expenses 118 rows Rs 1,346,603 (Shop 184,844 / Personal 1,161,759) | supplier nets match the workbook | import advance Rs", adv)
                print("unchanged: payment-account ledger totals, payments out (131 / Rs 6,352,404), receivables, inventory, Mohsin net payable")
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
