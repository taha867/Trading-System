from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.database import get_db
from src.pagination import PaginationParams
from src.sorting import SortDirection
from src.sales import service
from src.sales.constants import SalesLogExceptionKind
from src.sales.dependencies import valid_sales_order
from src.sales.models import SalesOrder
from src.sales.schemas import (
    InvoiceNumberRead,
    InvoiceOptionRead,
    LogExceptionInvoiceOptionRead,
    SalesLogExceptionListRead,
    SalesOrderCreate,
    SalesOrderDetailRead,
    SalesOrderListRead,
    SalesOrderRead,
)

sales_order_router = APIRouter(prefix="/sales-orders", tags=["sales"])
sales_log_exception_router = APIRouter(prefix="/sales-log-exceptions", tags=["sales"])


@sales_order_router.post("", response_model=SalesOrderRead, status_code=201)
async def create_sales_order(
    payload: SalesOrderCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.create_sales_order(db, payload)


@sales_order_router.get("", response_model=SalesOrderListRead)
async def list_sales_orders(
    # PaginationParams uses Depends() here (not Query()) because this endpoint also takes plain
    # filter params — FastAPI 0.141.1's Query()-model flattening stops working once any other
    # query param sits alongside it. Same workaround as inventory/router.py::list_stock_lots.
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
    search: str | None = None,
    invoice_number: str | None = None,
    party_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    item_id: int | None = None,
    sort: SortDirection = "newest",
):
    return await service.list_sales_orders(
        db,
        pagination,
        search=search,
        invoice_number=invoice_number,
        party_id=party_id,
        date_from=date_from,
        date_to=date_to,
        item_id=item_id,
        sort=sort,
    )


# Declared before "/{sales_order_id}" (as is "/invoice-numbers" below) so neither is parsed as an order id.
@sales_order_router.get("/invoice-options", response_model=list[InvoiceOptionRead])
async def list_invoice_options(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
    search: str | None = None,
):
    return await service.list_invoice_options(db, search)


# Declared before "/{sales_order_id}" so "invoice-numbers" is never parsed as an order id.
@sales_order_router.get("/invoice-numbers", response_model=list[InvoiceNumberRead])
async def get_invoice_numbers(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
    ids: Annotated[list[int], Query()] = [],  # noqa: B006 — FastAPI copies the default; never mutated
):
    return await service.get_invoice_numbers(db, ids)


@sales_order_router.get("/{sales_order_id}", response_model=SalesOrderDetailRead)
async def get_sales_order(
    sales_order: Annotated[SalesOrder, Depends(valid_sales_order)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.get_sales_order_detail(db, sales_order)


@sales_log_exception_router.get("/invoice-options", response_model=list[LogExceptionInvoiceOptionRead])
async def list_log_exception_invoice_options(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
    search: str | None = None,
):
    return await service.list_log_exception_invoice_options(db, search)


@sales_log_exception_router.get("/categories", response_model=list[str])
async def list_log_exception_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.list_log_exception_categories(db)


@sales_log_exception_router.get("", response_model=SalesLogExceptionListRead)
async def list_sales_log_exceptions(
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
    search: str | None = None,
    kind: SalesLogExceptionKind | None = None,
    party_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    invoice_number: str | None = None,
    category: str | None = None,
    sort: SortDirection = "newest",
):
    return await service.list_sales_log_exceptions(
        db,
        pagination,
        search=search,
        kind=kind,
        party_id=party_id,
        date_from=date_from,
        date_to=date_to,
        invoice_number=invoice_number,
        category=category,
        sort=sort,
    )


# Same shape as inventory/router.py: one exported `router` that main.py includes once.
router = APIRouter()
router.include_router(sales_order_router)
router.include_router(sales_log_exception_router)
