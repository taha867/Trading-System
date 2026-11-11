"""Turn the "no stock found" sales lines that now have stock into real sales.

230-odd September sales lines were saved as `sales_log_exception` rows of kind `insufficient_stock` because, when they
were imported, the item had no stock yet. Their money is already in the customer's balance (one Accounts Receivable
ledger row each). Since then the local purchases (and the catalog merge) have put stock in the app. For every such
line whose item is still active and whose FULL quantity is now available (the item's own stock first, then the items
that also fit, oldest first - the app's own `consume_stock_fifo` rule), this script:

  1. creates a real SalesOrder (one per invoice + customer + date; one line per item) taking that stock
     (SalesOrderLineLot rows, lot quantities down, 'sale' stock movements dated the sale date);
  2. keeps the customer's ledger exactly as it was: the first entry of the invoice group is re-pointed to the new
     order and set to the group total; the group's other entries are deleted (their amounts are inside that total);
  3. deletes the converted `sales_log_exception` rows (backup first).

Lines that cannot be covered in full, whose item no longer exists, or whose amount is not qty x rate stay as they are.
Nothing in the customer, supplier, cash or bank balances changes.

Default is a dry run (everything rolls back); --apply writes in ONE transaction with a JSON backup.

    PROD_DSN=postgresql://... python backend/scripts/oneoff/2026_11_12_convert_no_stock_sales.py [--apply]
"""
import asyncio
import collections
import json
import os
import re
import sys
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from sqlalchemy import select, text  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import src.main  # noqa: E402,F401  (loads every model so the table links resolve)
from src.catalog.models import Item  # noqa: E402
from src.inventory import service as inventory_service  # noqa: E402
from src.inventory.exceptions import InsufficientStock  # noqa: E402
from src.inventory.models import StockLot, StockMovement  # noqa: E402
from src.ledger.models import LedgerEntry  # noqa: E402
from src.sales.models import SalesLogException, SalesOrder, SalesOrderLine, SalesOrderLineLot  # noqa: E402

APPLY = "--apply" in sys.argv
BACKUP = Path(__file__).parent / "backups" / "2026_11_12_convert_no_stock_sales.json"
TWO = Decimal("0.01")


class Abort(Exception):
    pass


def need(cond, msg):
    if not cond:
        raise Abort(msg)


def money(v: Decimal) -> Decimal:
    return v.quantize(TWO, rounding=ROUND_HALF_UP)


async def fingerprint(db):
    return {
        "ledger": [tuple(r) for r in (await db.execute(text("select account, count(*), sum(debit), sum(credit) from ledger_entry group by 1 order by 1"))).all()],
        "parties": [tuple(r) for r in (await db.execute(text("select party_id, sum(debit - credit) from ledger_entry where party_id is not null group by 1 order by 1"))).all()],
        "accounts": [tuple(r) for r in (await db.execute(text("select payment_account_id, sum(debit - credit) from ledger_entry where payment_account_id is not null group by 1 order by 1"))).all()],
        "stock": tuple((await db.execute(text("select count(*), sum(qty_received), sum(qty_remaining), sum(qty_remaining * landed_cost_pkr) from stock_lot"))).one()),
        "moves": tuple((await db.execute(text("select count(*), sum(qty_delta) from stock_movement"))).one()),
        "orders": tuple((await db.execute(text("select count(*) from sales_order"))).one()),
        "exceptions": tuple((await db.execute(text("select count(*), sum(amount_pkr) from sales_log_exception where kind = 'insufficient_stock'"))).one()),
    }


async def main():
    dsn = os.environ["PROD_DSN"].replace("postgresql://", "postgresql+asyncpg://").split("?")[0]
    engine = create_async_engine(dsn, connect_args={"ssl": True})
    async with async_sessionmaker(engine, expire_on_commit=False)() as db:
        try:
            before = await fingerprint(db)
            exceptions = (
                await db.scalars(
                    select(SalesLogException)
                    .where(SalesLogException.kind == "insufficient_stock", SalesLogException.shown_only.is_(False))
                    .order_by(SalesLogException.entry_date, SalesLogException.id)
                )
            ).all()
            need(len(exceptions) == 231, f"expected 231 no-stock lines, found {len(exceptions)}")

            skipped = collections.Counter()
            groups: dict[tuple, list] = collections.OrderedDict()  # (invoice, party, date) -> [(exception, item_id)]
            plans = {}
            backup = {"deleted_exceptions": [], "ledger_before": {}, "ledger_deleted": [], "new_orders": []}
            converted_amount = Decimal(0)
            converted_lines = 0
            consumed_by_source = collections.Counter()
            cogs = Decimal(0)

            # Take stock line by line in date order inside ONE transaction; consume_stock_fifo moves the lot quantities
            # as it goes, so two lines can never claim the same pieces.
            for e in exceptions:
                m = re.search(r"item (\d+)", e.note or "")
                if not m:
                    skipped["no item in the note"] += 1
                    continue
                item_id = int(m.group(1))
                item = await db.get(Item, item_id)
                if item is None or not item.is_active:
                    skipped["item merged / renamed since the import"] += 1
                    continue
                if e.qty is None or e.rate_pkr is None or money(e.qty * e.rate_pkr) != e.amount_pkr:
                    skipped["amount is not qty x rate"] += 1
                    continue
                led = await db.get(LedgerEntry, e.ledger_entry_id) if e.ledger_entry_id else None
                if led is None or led.account != "Accounts Receivable" or led.debit != e.amount_pkr or led.party_id != e.party_id:
                    skipped["ledger row does not match"] += 1
                    continue
                try:
                    plan = await inventory_service.consume_stock_fifo(db, item_id=item_id, qty_needed=e.qty, movement_date=e.entry_date)
                except InsufficientStock:
                    skipped["not enough stock for the full quantity"] += 1
                    continue
                plans[e.id] = plan
                groups.setdefault((e.invoice_number or f"entry-{e.id}", e.party_id, e.entry_date), []).append((e, item_id))
                converted_lines += 1
                converted_amount += e.amount_pkr

            # one SalesOrder per group; an item twice in a group goes to a second order (an order has each item once)
            created = 0
            for (invoice, party_id, day), members in groups.items():
                layers: list[dict[int, tuple]] = []
                for e, item_id in members:
                    for layer in layers:
                        if item_id not in layer:
                            layer[item_id] = (e, item_id)
                            break
                    else:
                        layers.append({item_id: (e, item_id)})
                for layer in layers:
                    lines, total, group_entries = [], Decimal(0), []
                    for e, item_id in layer.values():
                        lines.append(
                            SalesOrderLine(
                                item_id=item_id, qty=e.qty, rate_pkr=e.rate_pkr,
                                consumptions=[SalesOrderLineLot(stock_lot_id=c.stock_lot_id, qty_consumed=c.qty_consumed, unit_cost_pkr=c.unit_cost_pkr) for c in plans[e.id]],
                            )
                        )
                        for c in plans[e.id]:
                            lot = await db.get(StockLot, c.stock_lot_id)
                            consumed_by_source[(await db.scalar(text("select po.source from purchase_order po join purchase_order_line pl on pl.purchase_order_id = po.id where pl.id = :i"), {"i": lot.purchase_order_line_id}))] += c.qty_consumed
                            cogs += money(c.qty_consumed * c.unit_cost_pkr)
                        total += money(e.qty * e.rate_pkr)
                        group_entries.append(e)
                    so = SalesOrder(party_id=party_id, order_date=day, invoice_number=invoice if not invoice.startswith("entry-") else None, lines=lines)
                    db.add(so)
                    await db.flush()
                    created += 1
                    keep = await db.get(LedgerEntry, group_entries[0].ledger_entry_id)
                    backup["ledger_before"][str(keep.id)] = {"debit": str(keep.debit), "reference_type": keep.reference_type, "reference_id": keep.reference_id}
                    keep.debit = money(total)
                    keep.reference_type = "sales_order"
                    keep.reference_id = so.id
                    backup["new_orders"].append(so.id)
                    for e in group_entries:
                        backup["deleted_exceptions"].append({c.name: str(getattr(e, c.name)) for c in SalesLogException.__table__.columns})
                        ledger_id = e.ledger_entry_id
                        e.ledger_entry_id = None
                        await db.flush()
                        if ledger_id != keep.id:
                            old = await db.get(LedgerEntry, ledger_id)
                            backup["ledger_deleted"].append({c.name: str(getattr(old, c.name)) for c in LedgerEntry.__table__.columns})
                            await db.delete(old)
                        await db.delete(e)
                    await db.flush()

            await db.flush()
            after = await fingerprint(db)
            # ---- verify: money untouched, stock down by exactly what was consumed
            need(before["parties"] == after["parties"], "a customer / supplier balance changed")
            need(before["accounts"] == after["accounts"], "a cash / bank balance changed")
            ar_b = [x for x in before["ledger"] if x[0] == "Accounts Receivable"][0]
            ar_a = [x for x in after["ledger"] if x[0] == "Accounts Receivable"][0]
            need(ar_b[2] == ar_a[2] and ar_b[3] == ar_a[3], "Accounts Receivable totals changed")
            consumed = sum(consumed_by_source.values(), Decimal(0))
            need(before["stock"][2] - after["stock"][2] == consumed, "stock lots did not go down by the consumed quantity")
            need(after["moves"][0] - before["moves"][0] == sum(len(p) for p in plans.values()), "wrong number of stock movements added")
            need(before["exceptions"][0] - after["exceptions"][0] == converted_lines, "wrong number of no-stock lines removed")
            need(before["exceptions"][1] - after["exceptions"][1] == converted_amount, "no-stock amount moved by the wrong total")
            need(await db.scalar(text("select count(*) from sales_order_line sol where not exists (select 1 from sales_order_line_lot x where x.sales_order_line_id = sol.id)")) == 0, "a sale line without stock")
            need(await db.scalar(text("select count(*) from stock_lot where qty_remaining < 0")) == 0, "a negative lot")

            print(f"{'APPLY' if APPLY else 'DRY RUN'}: converted {converted_lines} no-stock lines (Rs {converted_amount:,.2f}) into {created} real sales")
            print(f"  pieces taken from stock: {consumed}  ({dict((k, str(v)) for k, v in consumed_by_source.items())})")
            print(f"  cost of goods now in profit: Rs {cogs:,.2f}; margin on these lines: Rs {converted_amount - cogs:,.2f}")
            print(f"  still 'no stock': {before['exceptions'][0] - converted_lines} lines (Rs {before['exceptions'][1] - converted_amount:,.2f})")
            for reason, n in skipped.items():
                print(f"    - {n} lines left as they are: {reason}")
            print("  customer / supplier / cash / bank balances and Accounts Receivable totals: unchanged")
            if APPLY:
                BACKUP.parent.mkdir(exist_ok=True)
                BACKUP.write_text(json.dumps(backup, indent=0, default=str))
                await db.commit()
                print("committed")
            else:
                await db.rollback()
                print("rolled back (dry run) - nothing was changed")
        except Abort as exc:
            await db.rollback()
            print(f"ABORTED, nothing written: {exc}")
            sys.exit(1)
        except BaseException:
            await db.rollback()
            raise
    await engine.dispose()


asyncio.run(main())
