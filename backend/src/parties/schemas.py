from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from src.pagination import PaginatedResponse
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
    # Current running balance (opening balance + every ledger entry since) --
    # positive = the party owes the business (receivable), negative = the
    # business owes the party (payable). Attached by the service layer
    # (never a real ORM column) via a plain attribute set on the Party
    # instance before it's serialized.
    balance_pkr: Decimal


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


class PartyListRead(PaginatedResponse[PartyRead]):
    # Totals across every party matching the current filters, not just the
    # current page -- what the Parties list's summary bar shows.
    total_receivable_pkr: Decimal
    total_payable_pkr: Decimal
