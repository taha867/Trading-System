from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.payments.constants import PaymentDirection, PaymentReferenceType


class PaymentMethodCreate(BaseModel):
    name: Annotated[str, Field(max_length=64)]


class PaymentMethodRead(PaymentMethodCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool


class PaymentMethodUpdate(BaseModel):
    name: Annotated[str, Field(max_length=64)] | None = None


class PaymentAccountCreate(BaseModel):
    payment_method_id: int
    label: Annotated[str, Field(max_length=120)]
    account_number: Annotated[str, Field(max_length=64)] | None = None
    opening_balance: Annotated[Decimal, Field(decimal_places=2)] = Decimal(0)


class PaymentAccountRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    payment_method_id: int
    label: str
    account_number: str | None = None
    opening_balance: Decimal
    is_active: bool


class PaymentAccountUpdate(BaseModel):
    label: Annotated[str, Field(max_length=120)] | None = None
    account_number: Annotated[str, Field(max_length=64)] | None = None


class PaymentAccountBalanceRead(BaseModel):
    id: int
    label: str
    payment_method_id: int
    balance: Decimal


class PaymentTransactionCreate(BaseModel):
    payment_account_id: int
    direction: PaymentDirection
    amount: Annotated[Decimal, Field(gt=0, decimal_places=2)]
    transaction_date: date
    party_id: int | None = None
    reference_type: PaymentReferenceType | None = None
    reference_id: int | None = None
    note: Annotated[str, Field(max_length=255)] | None = None

    @model_validator(mode="after")
    def _reference_type_and_id_together(self) -> "PaymentTransactionCreate":
        if (self.reference_type is None) != (self.reference_id is None):
            raise ValueError("reference_type and reference_id must be set together")
        return self


class PaymentTransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    payment_account_id: int
    direction: PaymentDirection
    amount: Decimal
    transaction_date: date
    party_id: int | None = None
    reference_type: str | None = None
    reference_id: int | None = None
    note: str | None = None
    created_at: datetime
