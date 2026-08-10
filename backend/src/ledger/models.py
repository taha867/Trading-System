from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base


class LedgerEntry(Base):
    __tablename__ = "ledger_entry"

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_date: Mapped[date] = mapped_column(Date)
    account: Mapped[str]
    debit: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    credit: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    reference_type: Mapped[str | None] = mapped_column(nullable=True)
    reference_id: Mapped[int | None] = mapped_column(nullable=True)
    # Deferred from the Phase 0 migration (Party didn't exist yet) — now that it
    # does, this is the FK Phase 4/8 rely on for "a party's balance is just a
    # query over LedgerEntry filtered by party_id".
    party_id: Mapped[int | None] = mapped_column(ForeignKey("party.id"), nullable=True, index=True)
    payment_account_id: Mapped[int | None] = mapped_column(
        ForeignKey("payment_account.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
