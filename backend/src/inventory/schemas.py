from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, computed_field

from src.inventory.constants import StockMovementType
from src.inventory.utils import money


class StockLotReceiveCreate(BaseModel):
    purchase_order_line_id: int
    received_date: date


class StockLotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    purchase_order_line_id: int
    item_id: int
    qty_received: Decimal
    qty_remaining: Decimal
    landed_cost_pkr: Decimal
    received_date: date

    @computed_field
    @property
    def value_remaining_pkr(self) -> Decimal:
        return money(self.qty_remaining * self.landed_cost_pkr)


class StockMovementCreate(BaseModel):
    stock_lot_id: int
    qty_delta: Annotated[Decimal, Field(decimal_places=2)]
    reason: Annotated[str, Field(max_length=255)]
    movement_date: date
    # movement_type is not client-settable — every row created through this schema
    # is an "adjustment"; "receipt" rows are only ever created internally by
    # service.receive_purchase_order_line.


class StockMovementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    stock_lot_id: int
    movement_type: StockMovementType
    qty_delta: Decimal
    reason: str | None
    movement_date: date
    created_at: datetime
