from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.crud import build_crud_router
from src.database import get_db
from src.pagination import PaginatedResponse, PaginationParams
from src.purchasing import service
from src.purchasing.dependencies import valid_purchase_order
from src.purchasing.models import ExchangeRate, PurchaseOrder
from src.purchasing.schemas import (
    ExchangeRateCreate,
    ExchangeRateRead,
    ExchangeRateUpdate,
    PurchaseOrderCreate,
    PurchaseOrderRead,
)

exchange_rate_router = build_crud_router(
    model=ExchangeRate,
    create_schema=ExchangeRateCreate,
    read_schema=ExchangeRateRead,
    update_schema=ExchangeRateUpdate,
    prefix="/exchange-rates",
    tags=["purchasing"],
)

purchase_order_router = APIRouter(prefix="/purchase-orders", tags=["purchasing"])


@purchase_order_router.post("", response_model=PurchaseOrderRead, status_code=201)
async def create_purchase_order(
    payload: PurchaseOrderCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.create_purchase_order(db, payload)


@purchase_order_router.get("", response_model=PaginatedResponse[PurchaseOrderRead])
async def list_purchase_orders(
    pagination: Annotated[PaginationParams, Query()],
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.list_purchase_orders(db, pagination)


@purchase_order_router.get("/{purchase_order_id}", response_model=PurchaseOrderRead)
async def get_purchase_order(
    po: Annotated[PurchaseOrder, Depends(valid_purchase_order)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return po


router = APIRouter()
router.include_router(exchange_rate_router)
router.include_router(purchase_order_router)
