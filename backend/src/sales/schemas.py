from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, computed_field

from src.sales.utils import money


class SalesOrderLineCreate(BaseModel):
    item_id: int
    qty: Annotated[Decimal, Field(gt=0, decimal_places=2)]
    rate_pkr: Annotated[Decimal, Field(gt=0, decimal_places=2)]


class SalesOrderCreate(BaseModel):
    party_id: int
    order_date: date
    lines: Annotated[list[SalesOrderLineCreate], Field(min_length=1)]


class SalesOrderLineLotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stock_lot_id: int
    qty_consumed: Decimal
    unit_cost_pkr: Decimal


class SalesOrderLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    qty: Decimal
    rate_pkr: Decimal
    consumptions: list[SalesOrderLineLotRead]

    @computed_field
    @property
    def amount_pkr(self) -> Decimal:
        return money(self.qty * self.rate_pkr)

    @computed_field
    @property
    def cost_pkr(self) -> Decimal:
        return money(sum((c.qty_consumed * c.unit_cost_pkr for c in self.consumptions), Decimal(0)))

    @computed_field
    @property
    def margin_pkr(self) -> Decimal:
        return money(self.amount_pkr - self.cost_pkr)


class SalesOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    party_id: int
    order_date: date
    created_at: datetime
    lines: list[SalesOrderLineRead]

    @computed_field
    @property
    def total_pkr(self) -> Decimal:
        return money(sum((line.amount_pkr for line in self.lines), Decimal(0)))

    @computed_field
    @property
    def total_margin_pkr(self) -> Decimal:
        return money(sum((line.margin_pkr for line in self.lines), Decimal(0)))
