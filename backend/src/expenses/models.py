from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base


class ExpenseCategory(Base):
    __tablename__ = "expense_category"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    frequency: Mapped[str]  # "daily" | "monthly" — Literal enforced at the Pydantic layer, see constants.py
    is_active: Mapped[bool] = mapped_column(default=True)


class RecurringExpenseTemplate(Base):
    __tablename__ = "recurring_expense_template"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]  # e.g. "Shop rent", "Staff salaries"
    category_id: Mapped[int] = mapped_column(ForeignKey("expense_category.id"), index=True)
    payment_account_id: Mapped[int] = mapped_column(ForeignKey("payment_account.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    day_of_month: Mapped[int | None] = mapped_column(nullable=True)  # informational only, not used to auto-trigger
    description: Mapped[str | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)


class Expense(Base):
    __tablename__ = "expense"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("expense_category.id"), index=True)
    payment_account_id: Mapped[int] = mapped_column(ForeignKey("payment_account.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    expense_date: Mapped[date] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(nullable=True)
    status: Mapped[str]  # "draft" | "confirmed" — no column default, see constants.py (the two entry points disagree)
    recurring_template_id: Mapped[int | None] = mapped_column(
        ForeignKey("recurring_expense_template.id"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
