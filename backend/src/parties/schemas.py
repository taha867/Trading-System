from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from src.parties.constants import PartyRole


class PartyCreate(BaseModel):
    name: Annotated[str, Field(max_length=120)]
    contact: Annotated[str | None, Field(max_length=64)] = None
    address: Annotated[str | None, Field(max_length=255)] = None
    roles: Annotated[list[PartyRole], Field(min_length=1)]
    opening_balance: Decimal = Decimal(0)


class PartyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    contact: str | None
    address: str | None
    roles: list[PartyRole]
    opening_balance: Decimal
    is_active: bool


class PartyUpdate(BaseModel):
    name: Annotated[str, Field(max_length=120)] | None = None
    contact: Annotated[str | None, Field(max_length=64)] = None
    address: Annotated[str | None, Field(max_length=255)] = None
    roles: Annotated[list[PartyRole], Field(min_length=1)] | None = None
    # opening_balance is intentionally NOT updatable — it's a write-once value
    # posted to the ledger at creation (see service.create_party); changing it
    # later would desync the party's ledger history from this column.


class PartyStatementEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entry_date: date
    account: str
    debit: Decimal
    credit: Decimal
    reference_type: str | None
    reference_id: int | None
    running_balance: Decimal


class PartyStatementRead(BaseModel):
    party: PartyRead
    opening_balance: Decimal
    entries: list[PartyStatementEntryRead]
    closing_balance: Decimal
