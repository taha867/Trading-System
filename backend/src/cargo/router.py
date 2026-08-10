from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.cargo import service
from src.cargo.dependencies import valid_cargo_shipment
from src.cargo.models import CargoCostBasis, CargoMode, CargoShipment
from src.cargo.schemas import (
    CargoCostBasisCreate,
    CargoCostBasisRead,
    CargoCostBasisUpdate,
    CargoModeCreate,
    CargoModeRead,
    CargoModeUpdate,
    CargoShipmentCreate,
    CargoShipmentRead,
)
from src.crud import build_crud_router
from src.database import get_db
from src.pagination import PaginatedResponse, PaginationParams

cargo_mode_router = build_crud_router(
    model=CargoMode,
    create_schema=CargoModeCreate,
    read_schema=CargoModeRead,
    update_schema=CargoModeUpdate,
    prefix="/modes",
    tags=["cargo"],
)

cargo_cost_basis_router = build_crud_router(
    model=CargoCostBasis,
    create_schema=CargoCostBasisCreate,
    read_schema=CargoCostBasisRead,
    update_schema=CargoCostBasisUpdate,
    prefix="/cost-bases",
    tags=["cargo"],
)

cargo_shipment_router = APIRouter(prefix="/shipments", tags=["cargo"])


@cargo_shipment_router.post("", response_model=CargoShipmentRead, status_code=201)
async def create_shipment(
    payload: CargoShipmentCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.create_shipment(db, payload)


@cargo_shipment_router.get("", response_model=PaginatedResponse[CargoShipmentRead])
async def list_shipments(
    pagination: Annotated[PaginationParams, Query()],
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.list_shipments(db, pagination)


@cargo_shipment_router.get("/{cargo_shipment_id}", response_model=CargoShipmentRead)
async def get_shipment(
    shipment: Annotated[CargoShipment, Depends(valid_cargo_shipment)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return shipment


router = APIRouter()
router.include_router(cargo_mode_router)
router.include_router(cargo_cost_basis_router)
router.include_router(cargo_shipment_router)
