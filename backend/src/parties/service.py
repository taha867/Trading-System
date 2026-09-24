from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import ConflictException
from src.ledger import service as ledger_service
from src.ledger.models import LedgerEntry
from src.pagination import PaginationParams
from src.parties.constants import PartyRole
from src.parties.exceptions import PartyNotFound, PartyRoleMismatch
from src.parties.models import Party
from src.parties.schemas import (
    PartyCreate,
    PartyListRead,
    PartyRead,
    PartyStatementEntryRead,
    PartyStatementRead,
    PartyUpdate,
)


async def get_active_party(db: AsyncSession, party_id: int) -> Party:
    party = await db.get(Party, party_id)
    if not party or not party.is_active:
        raise PartyNotFound()
    return party


def ensure_role(party: Party, role: PartyRole) -> Party:
    if role.value not in party.roles:
        raise PartyRoleMismatch(f"Party {party.id} does not hold the '{role.value}' role")
    return party


def ensure_any_role(party: Party, roles: tuple[PartyRole, ...]) -> Party:
    if not any(role.value in party.roles for role in roles):
        names = " or ".join(role.value for role in roles)
        raise PartyRoleMismatch(f"Party {party.id} does not hold any of: {names}")
    return party


def _balance_subquery():
    return (
        select(LedgerEntry.party_id.label("party_id"), func.sum(LedgerEntry.debit - LedgerEntry.credit).label("balance"))
        .group_by(LedgerEntry.party_id)
        .subquery()
    )


async def list_parties(
    db: AsyncSession, pagination: PaginationParams, search: str | None = None, role: str | None = None
) -> PartyListRead:
    offset = (pagination.page - 1) * pagination.page_size

    conditions = [Party.is_active.is_(True)]
    if search is not None:
        conditions.append(Party.name.ilike(f"%{search}%"))
    if role is not None:
        conditions.append(Party.roles.contains([role]))

    total = await db.scalar(select(func.count()).select_from(Party).where(*conditions))

    balance_subq = _balance_subquery()
    balance_col = func.coalesce(balance_subq.c.balance, 0)
    rows = (
        await db.execute(
            select(Party, balance_col.label("balance_pkr"))
            .outerjoin(balance_subq, balance_subq.c.party_id == Party.id)
            .where(*conditions)
            .order_by(Party.id)
            .offset(offset)
            .limit(pagination.page_size)
        )
    ).all()
    items = []
    for party, balance_pkr in rows:
        party.balance_pkr = balance_pkr
        items.append(party)

    # Totals across every party matching the filters, not just this page.
    all_balances = (
        await db.execute(
            select(balance_col).select_from(Party).outerjoin(balance_subq, balance_subq.c.party_id == Party.id).where(*conditions)
        )
    ).scalars().all()
    total_receivable_pkr = sum((b for b in all_balances if b > 0), Decimal(0))
    total_payable_pkr = -sum((b for b in all_balances if b < 0), Decimal(0))

    return PartyListRead(
        items=items,
        total=total or 0,
        page=pagination.page,
        page_size=pagination.page_size,
        total_receivable_pkr=total_receivable_pkr,
        total_payable_pkr=total_payable_pkr,
    )


async def attach_balance(db: AsyncSession, party: Party) -> Party:
    balance = await db.scalar(
        select(func.sum(LedgerEntry.debit - LedgerEntry.credit)).where(LedgerEntry.party_id == party.id)
    )
    party.balance_pkr = balance or Decimal(0)
    return party


async def create_party(db: AsyncSession, payload: PartyCreate) -> Party:
    party = Party(
        name=payload.name,
        contact=payload.contact,
        address=payload.address,
        roles=[role.value for role in payload.roles],
        opening_balance=payload.opening_balance,
    )
    db.add(party)

    if payload.opening_balance != 0:
        await db.flush()  # party.id is needed for the ledger entry below
        if payload.opening_balance > 0:
            debit, credit = payload.opening_balance, Decimal(0)
        else:
            debit, credit = Decimal(0), -payload.opening_balance
        await ledger_service.post_entry(
            db,
            entry_date=date.today(),
            account="Party Opening Balance",
            debit=debit,
            credit=credit,
            reference_type="party_opening_balance",
            reference_id=party.id,
            party_id=party.id,
        )

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictException("Party could not be saved") from exc
    await db.refresh(party)
    return await attach_balance(db, party)


async def update_party(db: AsyncSession, party: Party, payload: PartyUpdate) -> Party:
    updates = payload.model_dump(exclude_unset=True)
    if "roles" in updates and updates["roles"] is not None:
        updates["roles"] = [role.value for role in payload.roles]
    for field, value in updates.items():
        setattr(party, field, value)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictException("Party could not be saved") from exc
    await db.refresh(party)
    return await attach_balance(db, party)


async def soft_delete_party(db: AsyncSession, party: Party) -> None:
    party.is_active = False
    await db.commit()


async def get_party_statement(db: AsyncSession, party: Party) -> PartyStatementRead:
    # The "party_opening_balance" ledger entry (posted once, at party creation --
    # see create_party) exists so aggregate reports that sum LedgerEntry rows
    # (e.g. reporting.get_balance_statement) see the opening balance without any
    # special-casing. Here it must be excluded from `entries`: `running` already
    # seeds from party.opening_balance below, so including that same entry too
    # would double-count it -- the frontend's own separate "Opening balance" row
    # already represents it.
    result = await db.execute(
        select(LedgerEntry)
        .where(LedgerEntry.party_id == party.id, LedgerEntry.reference_type != "party_opening_balance")
        .order_by(LedgerEntry.entry_date, LedgerEntry.id)
    )
    rows = result.scalars().all()

    running = party.opening_balance
    entries: list[PartyStatementEntryRead] = []
    for row in rows:
        running += row.debit - row.credit
        entries.append(
            PartyStatementEntryRead(
                id=row.id,
                entry_date=row.entry_date,
                account=row.account,
                debit=row.debit,
                credit=row.credit,
                reference_type=row.reference_type,
                reference_id=row.reference_id,
                running_balance=running,
            )
        )

    # `running` at this point already equals the same figure attach_balance would
    # compute (opening_balance plus every real ledger entry) -- reuse it instead
    # of a second query.
    party.balance_pkr = running
    return PartyStatementRead(
        party=PartyRead.model_validate(party),
        opening_balance=party.opening_balance,
        entries=entries,
        closing_balance=running,
    )
