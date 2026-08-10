from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database import get_db
from src.sales.exceptions import SalesOrderNotFound
from src.sales.models import SalesOrder, SalesOrderLine


async def valid_sales_order(sales_order_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> SalesOrder:
    # select().options(selectinload(...)), not db.get() — same reasoning as
    # purchasing.dependencies.valid_purchase_order: db.get() silently ignores loader
    # options when it serves the object from the identity map.
    result = await db.execute(
        select(SalesOrder)
        .options(selectinload(SalesOrder.lines).selectinload(SalesOrderLine.consumptions))
        .where(SalesOrder.id == sales_order_id)
    )
    so = result.scalar_one_or_none()
    if not so:
        raise SalesOrderNotFound()
    return so
