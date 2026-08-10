from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from src.purchasing.constants import PurchaseOrderSource
from src.purchasing.utils import money


class ExchangeRateCreate(BaseModel):
    rate_date: date
    rate: Annotated[Decimal, Field(gt=0, decimal_places=4)]


class ExchangeRateRead(ExchangeRateCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool


class ExchangeRateUpdate(BaseModel):
    rate: Annotated[Decimal, Field(gt=0, decimal_places=4)] | None = None


class PurchaseOrderLineCreate(BaseModel):
    item_id: int
    qty: Annotated[Decimal, Field(gt=0, decimal_places=2)]
    # Exactly one of these two is required, enforced by PurchaseOrderCreate's validator
    # against the order's own `source` — a china line prices in RMB (rate_pkr is derived
    # from that day's ExchangeRate), a local line is quoted directly in PKR.
    rate_rmb: Annotated[Decimal, Field(gt=0, decimal_places=2)] | None = None
    rate_pkr: Annotated[Decimal, Field(gt=0, decimal_places=2)] | None = None


class PurchaseOrderLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    qty: Decimal
    rate_rmb: Decimal | None = None
    rate_pkr: Decimal
    landed_cost_pkr: Decimal | None = None

    @computed_field
    @property
    def amount_rmb(self) -> Decimal | None:
        return money(self.qty * self.rate_rmb) if self.rate_rmb is not None else None

    @computed_field
    @property
    def amount_pkr(self) -> Decimal:
        return money(self.qty * self.rate_pkr)

    @computed_field
    @property
    def amount_landed_pkr(self) -> Decimal | None:
        return money(self.qty * self.landed_cost_pkr) if self.landed_cost_pkr is not None else None


class PurchaseOrderCreate(BaseModel):
    party_id: int
    order_date: date
    source: PurchaseOrderSource = "china"
    lines: Annotated[list[PurchaseOrderLineCreate], Field(min_length=1)]

    @model_validator(mode="after")
    def _validate_line_rates_match_source(self) -> "PurchaseOrderCreate":
        for i, line in enumerate(self.lines):
            if self.source == "china":
                if line.rate_rmb is None or line.rate_pkr is not None:
                    raise ValueError(f"line {i}: china-sourced lines must set rate_rmb, not rate_pkr")
            else:
                if line.rate_pkr is None or line.rate_rmb is not None:
                    raise ValueError(f"line {i}: local-sourced lines must set rate_pkr, not rate_rmb")
        return self


class PurchaseOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    party_id: int
    order_date: date
    source: PurchaseOrderSource
    status: str
    lines: list[PurchaseOrderLineRead]

    @computed_field
    @property
    def total_rmb(self) -> Decimal | None:
        # None (not 0) when any line lacks an RMB rate — a real all-local order's total
        # isn't "zero RMB", it just isn't priced in RMB at all. Keyed on the lines' own
        # data, not on `source`, so a china order with one hand-fixed NULL rate_rmb line
        # can't crash this sum instead of just reporting itself as unpriced-in-RMB.
        amounts = [line.amount_rmb for line in self.lines]
        if any(amount is None for amount in amounts):
            return None
        return money(sum(amounts, Decimal(0)))

    @computed_field
    @property
    def total_pkr(self) -> Decimal:
        return money(sum((line.amount_pkr for line in self.lines), Decimal(0)))
