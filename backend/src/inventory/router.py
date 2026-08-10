from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.database import get_db
from src.inventory import service
from src.inventory.dependencies import valid_stock_lot
from src.inventory.models import StockLot
from src.inventory.schemas import (
    StockLotRead,
    StockLotReceiveCreate,
    StockMovementCreate,
    StockMovementRead,
)
from src.pagination import PaginatedResponse, PaginationParams

stock_lot_router = APIRouter(prefix="/stock-lots", tags=["inventory"])


@stock_lot_router.post("", response_model=StockLotRead, status_code=201)
async def receive_line(
    payload: StockLotReceiveCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.receive_purchase_order_line(db, payload)


@stock_lot_router.get("", response_model=PaginatedResponse[StockLotRead])
async def list_stock_lots(
    # PaginationParams uses Depends() here rather than crud.py/other routers' Query() —
    # this endpoint also takes plain filter params (item_id/stock_lot_id/
    # include_depleted), and FastAPI 0.141.1's Query()-model flattening stops working
    # once any other query param sits alongside it (confirmed via isolated repro).
    # Depends() as a sub-dependency class doesn't have that limitation.
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
    item_id: int | None = None,
    include_depleted: bool = False,
):
    return await service.list_stock_lots(db, pagination, item_id, include_depleted)


@stock_lot_router.get("/{stock_lot_id}", response_model=StockLotRead)
async def get_stock_lot(
    lot: Annotated[StockLot, Depends(valid_stock_lot)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return lot


stock_movement_router = APIRouter(prefix="/stock-movements", tags=["inventory"])


@stock_movement_router.post("", response_model=StockMovementRead, status_code=201)
async def create_adjustment(
    payload: StockMovementCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.create_adjustment(db, payload)


@stock_movement_router.get("", response_model=PaginatedResponse[StockMovementRead])
async def list_stock_movements(
    # PaginationParams uses Depends() here rather than crud.py/other routers' Query() —
    # this endpoint also takes plain filter params (item_id/stock_lot_id/
    # include_depleted), and FastAPI 0.141.1's Query()-model flattening stops working
    # once any other query param sits alongside it (confirmed via isolated repro).
    # Depends() as a sub-dependency class doesn't have that limitation.
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
    stock_lot_id: int | None = None,
):
    return await service.list_stock_movements(db, pagination, stock_lot_id)


router = APIRouter()
router.include_router(stock_lot_router)
router.include_router(stock_movement_router)
