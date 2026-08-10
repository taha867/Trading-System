from datetime import date
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import ConflictException
from src.ledger import service as ledger_service
from src.ledger.models import LedgerEntry
from src.pagination import PaginatedResponse, PaginationParams
from src.parties.constants import PartyRole
from src.parties.exceptions import PartyNotFound, PartyRoleMismatch
from src.parties.models import Party
from src.parties.schemas import (
    PartyCreate,
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


async def list_parties(db: AsyncSession, pagination: PaginationParams) -> PaginatedResponse[PartyRead]:
    offset = (pagination.page - 1) * pagination.page_size

    total = await db.scalar(select(func.count()).select_from(Party).where(Party.is_active.is_(True)))
    result = await db.execute(
        select(Party).where(Party.is_active.is_(True)).order_by(Party.id).offset(offset).limit(pagination.page_size)
    )
    items = result.scalars().all()

    return PaginatedResponse[PartyRead](
        items=items,
        total=total or 0,
        page=pagination.page,
        page_size=pagination.page_size,
    )


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
    return party


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
    return party


async def soft_delete_party(db: AsyncSession, party: Party) -> None:
    party.is_active = False
    await db.commit()


async def get_party_statement(db: AsyncSession, party: Party) -> PartyStatementRead:
    result = await db.execute(
        select(LedgerEntry)
        .where(LedgerEntry.party_id == party.id)
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

    return PartyStatementRead(
        party=PartyRead.model_validate(party),
        opening_balance=party.opening_balance,
        entries=entries,
        closing_balance=running,
    )
