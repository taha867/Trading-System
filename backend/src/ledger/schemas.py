from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class LedgerEntryRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entry_date: date
    account: str
    debit: Decimal
    credit: Decimal
    reference_type: str | None
    reference_id: int | None
    party_id: int | None
    created_at: datetime
