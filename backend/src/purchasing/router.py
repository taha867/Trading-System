from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.crud import build_crud_router
from src.database import get_db
from src.pagination import PaginationParams
from src.sorting import SortDirection
from src.purchasing import service
from src.purchasing.constants import PurchaseOrderSource, PurchaseOrderStatus
from src.purchasing.dependencies import valid_purchase_order
from src.purchasing.models import ExchangeRate, PurchaseOrder
from src.purchasing.schemas import (
    ExchangeRateCreate,
    ExchangeRateRead,
    ExchangeRateUpdate,
    InvoiceNumberRead,
    InvoiceOptionRead,
    LogExceptionInvoiceOptionRead,
    PurchaseLogExceptionListRead,
    PurchaseOrderCreate,
    PurchaseOrderDetailRead,
    PurchaseOrderListRead,
    PurchaseOrderRead,
)

exchange_rate_router = build_crud_router(
    model=ExchangeRate,
    create_schema=ExchangeRateCreate,
    read_schema=ExchangeRateRead,
    update_schema=ExchangeRateUpdate,
    prefix="/exchange-rates",
    tags=["purchasing"],
    date_filters=["rate_date"],
)

purchase_order_router = APIRouter(prefix="/purchase-orders", tags=["purchasing"])
purchase_log_exception_router = APIRouter(prefix="/purchase-log-exceptions", tags=["purchasing"])


@purchase_order_router.post("", response_model=PurchaseOrderRead, status_code=201)
async def create_purchase_order(
    payload: PurchaseOrderCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.create_purchase_order(db, payload)


@purchase_order_router.get("", response_model=PurchaseOrderListRead)
async def list_purchase_orders(
    # PaginationParams uses Depends() here (not Query()) because this endpoint also takes plain
    # filter params — FastAPI 0.141.1's Query()-model flattening stops working once any other
    # query param sits alongside it. Same workaround as sales/router.py::list_sales_orders.
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
    search: str | None = None,
    invoice_number: str | None = None,
    party_id: int | None = None,
    source: PurchaseOrderSource | None = None,
    status: PurchaseOrderStatus | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    item_id: int | None = None,
    sort: SortDirection = "newest",
):
    return await service.list_purchase_orders(
        db,
        pagination,
        search=search,
        invoice_number=invoice_number,
        party_id=party_id,
        source=source,
        status=status,
        date_from=date_from,
        date_to=date_to,
        item_id=item_id,
        sort=sort,
    )


# Declared before "/{purchase_order_id}" so "invoice-options" and "invoice-numbers" are never
# parsed as an order id.
@purchase_order_router.get("/invoice-options", response_model=list[InvoiceOptionRead])
async def list_invoice_options(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
    search: str | None = None,
):
    return await service.list_invoice_options(db, search)


@purchase_order_router.get("/invoice-numbers", response_model=list[InvoiceNumberRead])
async def get_invoice_numbers(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
    ids: Annotated[list[int], Query()] = [],  # noqa: B006 — FastAPI copies the default; never mutated
):
    return await service.get_invoice_numbers(db, ids)


@purchase_order_router.get("/{purchase_order_id}", response_model=PurchaseOrderDetailRead)
async def get_purchase_order(
    po: Annotated[PurchaseOrder, Depends(valid_purchase_order)],
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.get_purchase_order_detail(db, po)


@purchase_log_exception_router.get("/invoice-options", response_model=list[LogExceptionInvoiceOptionRead])
async def list_log_exception_invoice_options(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
    search: str | None = None,
):
    return await service.list_log_exception_invoice_options(db, search)


@purchase_log_exception_router.get("/categories", response_model=list[str])
async def list_log_exception_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.list_log_exception_categories(db)


@purchase_log_exception_router.get("", response_model=PurchaseLogExceptionListRead)
async def list_purchase_log_exceptions(
    pagination: Annotated[PaginationParams, Depends()],
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
    search: str | None = None,
    party_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    invoice_number: str | None = None,
    category: str | None = None,
    sort: SortDirection = "newest",
):
    return await service.list_purchase_log_exceptions(
        db,
        pagination,
        search=search,
        party_id=party_id,
        date_from=date_from,
        date_to=date_to,
        invoice_number=invoice_number,
        category=category,
        sort=sort,
    )


router = APIRouter()
router.include_router(exchange_rate_router)
router.include_router(purchase_order_router)
router.include_router(purchase_log_exception_router)
