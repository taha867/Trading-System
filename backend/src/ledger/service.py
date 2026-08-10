from datetime import date
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from src.ledger.models import LedgerEntry


async def post_entry(
    db: AsyncSession,
    *,
    entry_date: date,
    account: str,
    reference_type: str,
    reference_id: int,
    debit: Decimal = Decimal(0),
    credit: Decimal = Decimal(0),
    party_id: int | None = None,
    payment_account_id: int | None = None,
) -> LedgerEntry:
    # Deliberately does not commit (or flush) — the caller wraps this call and its own
    # domain writes in one transaction, ending in a single `await db.commit()`, so a
    # domain row and its ledger entry always land together or not at all.
    entry = LedgerEntry(
        entry_date=entry_date,
        account=account,
        debit=debit,
        credit=credit,
        reference_type=reference_type,
        reference_id=reference_id,
        party_id=party_id,
        payment_account_id=payment_account_id,
    )
    db.add(entry)
    return entry
