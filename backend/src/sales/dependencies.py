from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.catalog.models import Item
from src.database import get_db
from src.sales.exceptions import SalesOrderNotFound
from src.sales.models import SalesOrder, SalesOrderLine

# Reused everywhere a SalesOrder's lines are loaded — SalesOrderLineRead's
# item_sku/item_variant/model_name/category_name properties need this whole
# chain eagerly loaded (lazy="raise" on every hop) or serialization blows up.
SALES_ORDER_LOAD_OPTIONS = (
    selectinload(SalesOrder.lines).selectinload(SalesOrderLine.consumptions),
    selectinload(SalesOrder.lines).joinedload(SalesOrderLine.item).joinedload(Item.model),
    selectinload(SalesOrder.lines).joinedload(SalesOrderLine.item).joinedload(Item.category),
)


async def valid_sales_order(sales_order_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> SalesOrder:
    # select().options(selectinload(...)), not db.get() — same reasoning as
    # purchasing.dependencies.valid_purchase_order: db.get() silently ignores loader
    # options when it serves the object from the identity map.
    result = await db.execute(
        select(SalesOrder)
        .options(*SALES_ORDER_LOAD_OPTIONS)
        .where(SalesOrder.id == sales_order_id)
    )
    so = result.scalar_one_or_none()
    if not so:
        raise SalesOrderNotFound()
    return so
