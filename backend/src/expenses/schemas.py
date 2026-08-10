from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from src.expenses.constants import ExpenseCategoryFrequency, ExpenseStatus


class ExpenseCategoryCreate(BaseModel):
    name: Annotated[str, Field(max_length=120)]
    frequency: ExpenseCategoryFrequency


class ExpenseCategoryRead(ExpenseCategoryCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool


class ExpenseCategoryUpdate(BaseModel):
    name: Annotated[str, Field(max_length=120)] | None = None
    frequency: ExpenseCategoryFrequency | None = None


class RecurringExpenseTemplateCreate(BaseModel):
    name: Annotated[str, Field(max_length=120)]
    category_id: int
    payment_account_id: int
    amount: Annotated[Decimal, Field(gt=0, decimal_places=2)]
    day_of_month: Annotated[int, Field(ge=1, le=28)] | None = None
    description: Annotated[str, Field(max_length=255)] | None = None


class RecurringExpenseTemplateRead(RecurringExpenseTemplateCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool


class RecurringExpenseTemplateUpdate(BaseModel):
    name: Annotated[str, Field(max_length=120)] | None = None
    category_id: int | None = None
    payment_account_id: int | None = None
    amount: Annotated[Decimal, Field(gt=0, decimal_places=2)] | None = None
    day_of_month: Annotated[int, Field(ge=1, le=28)] | None = None
    description: Annotated[str, Field(max_length=255)] | None = None


class ExpenseCreate(BaseModel):
    category_id: int
    payment_account_id: int
    amount: Annotated[Decimal, Field(gt=0, decimal_places=2)]
    expense_date: date
    description: Annotated[str, Field(max_length=255)] | None = None


class ExpenseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    category_id: int
    payment_account_id: int
    amount: Decimal
    expense_date: date
    description: str | None = None
    status: ExpenseStatus
    recurring_template_id: int | None = None
    created_at: datetime
