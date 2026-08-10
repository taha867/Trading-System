from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

from src.cargo.constants import CargoCostBasisCode


class CargoModeCreate(BaseModel):
    name: Annotated[str, Field(max_length=64)]


class CargoModeRead(CargoModeCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool


class CargoModeUpdate(BaseModel):
    name: Annotated[str, Field(max_length=64)] | None = None


class CargoCostBasisCreate(BaseModel):
    name: Annotated[str, Field(max_length=64)]
    code: CargoCostBasisCode


class CargoCostBasisRead(CargoCostBasisCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool


class CargoCostBasisUpdate(BaseModel):
    name: Annotated[str, Field(max_length=64)] | None = None
    # `code` intentionally omitted — pinned at creation, the allocation service branches on it


class CargoAllocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    purchase_order_line_id: int
    basis_value: Decimal
    allocated_cost_pkr: Decimal


class CargoShipmentLineInput(BaseModel):
    purchase_order_line_id: int
    basis_value: Annotated[Decimal, Field(gt=0, decimal_places=4)] | None = None


class CargoShipmentCreate(BaseModel):
    cargo_agent_id: int
    cargo_mode_id: int
    cost_basis_id: int
    shipment_date: date
    total_cost_pkr: Annotated[Decimal, Field(gt=0, decimal_places=2)]
    purchase_order_ids: Annotated[list[int], Field(min_length=1)]
    line_basis_values: list[CargoShipmentLineInput] = []


class CargoShipmentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    cargo_agent_id: int
    cargo_mode_id: int
    cost_basis_id: int
    shipment_date: date
    total_cost_pkr: Decimal
    allocations: list[CargoAllocationRead]
