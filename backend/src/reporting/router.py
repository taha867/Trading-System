from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.dependencies import get_current_user
from src.auth.models import User
from src.database import get_db
from src.reporting import service
from src.reporting.constants import DEFAULT_WINDOW_DAYS, MAX_WINDOW_DAYS, MIN_WINDOW_DAYS
from src.reporting.schemas import (
    BalanceStatementRead,
    MarginReportRead,
    ReorderPriorityRead,
    SellThroughRead,
    StockListRead,
)

router = APIRouter(tags=["reporting"])  # no own prefix — main.py's is the only one, matches parties/router.py

WindowDays = Annotated[int, Query(ge=MIN_WINDOW_DAYS, le=MAX_WINDOW_DAYS)]


@router.get("/balance-statement", response_model=BalanceStatementRead)
async def balance_statement(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
):
    return await service.get_balance_statement(db)


@router.get("/sell-through", response_model=SellThroughRead)
async def sell_through(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
    window_days: WindowDays = DEFAULT_WINDOW_DAYS,
):
    return await service.get_sell_through(db, window_days)


@router.get("/reorder-priority", response_model=ReorderPriorityRead)
async def reorder_priority(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
    window_days: WindowDays = DEFAULT_WINDOW_DAYS,
):
    return await service.recalculate_reorder_priority(db, window_days)


@router.get("/margin", response_model=MarginReportRead)
async def margin_report(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
    window_days: WindowDays = DEFAULT_WINDOW_DAYS,
):
    return await service.get_margin_report(db, window_days)


@router.get("/stock-list", response_model=StockListRead)
async def stock_list(
    db: Annotated[AsyncSession, Depends(get_db)],
    _current_user: Annotated[User, Depends(get_current_user)],
    in_stock_only: bool = True,
):
    return await service.get_stock_list(db, in_stock_only)
