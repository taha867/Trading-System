from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base


class PaymentMethod(Base):
    __tablename__ = "payment_method"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    is_active: Mapped[bool] = mapped_column(default=True)


class PaymentAccount(Base):
    __tablename__ = "payment_account"

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_method_id: Mapped[int] = mapped_column(ForeignKey("payment_method.id"), index=True)
    label: Mapped[str]
    account_number: Mapped[str | None] = mapped_column(nullable=True)
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    is_active: Mapped[bool] = mapped_column(default=True)


class PaymentTransaction(Base):
    __tablename__ = "payment_transaction"

    id: Mapped[int] = mapped_column(primary_key=True)
    payment_account_id: Mapped[int] = mapped_column(ForeignKey("payment_account.id"), index=True)
    direction: Mapped[str]
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    transaction_date: Mapped[date] = mapped_column(Date)
    party_id: Mapped[int | None] = mapped_column(ForeignKey("party.id"), nullable=True, index=True)
    reference_type: Mapped[str | None] = mapped_column(nullable=True)
    reference_id: Mapped[int | None] = mapped_column(nullable=True)
    note: Mapped[str | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
