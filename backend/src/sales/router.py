from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.database import get_db
from src.pagination import PaginatedResponse, PaginationParams
from src.sales import service
from src.sales.dependencies import valid_sales_order
from src.sales.models import SalesOrder
from src.sales.schemas import SalesOrderCreate, SalesOrderRead

router = APIRouter(prefix="/sales-orders", tags=["sales"])


@router.post("", response_model=SalesOrderRead, status_code=201)
async def create_sales_order(
    payload: SalesOrderCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.create_sales_order(db, payload)


@router.get("", response_model=PaginatedResponse[SalesOrderRead])
async def list_sales_orders(
    pagination: Annotated[PaginationParams, Query()],
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.list_sales_orders(db, pagination)


@router.get("/{sales_order_id}", response_model=SalesOrderRead)
async def get_sales_order(
    sales_order: Annotated[SalesOrder, Depends(valid_sales_order)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return sales_order
