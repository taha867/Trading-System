from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.catalog.models import Item
from src.database import get_db
from src.purchasing.exceptions import PurchaseOrderNotFound
from src.purchasing.models import PurchaseOrder, PurchaseOrderLine

# Reused everywhere a PurchaseOrder's lines are loaded — PurchaseOrderLineRead's
# item_sku/item_variant/model_name/category_name properties need this whole
# chain eagerly loaded (lazy="raise" on every hop) or serialization blows up.
PURCHASE_ORDER_LOAD_OPTIONS = (
    selectinload(PurchaseOrder.lines).joinedload(PurchaseOrderLine.item).joinedload(Item.model),
    selectinload(PurchaseOrder.lines).joinedload(PurchaseOrderLine.item).joinedload(Item.category),
)


async def valid_purchase_order(purchase_order_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> PurchaseOrder:
    # select().options(selectinload(...)), not db.get() — Session.get() silently
    # ignores loader options when it serves the object from the identity map.
    result = await db.execute(
        select(PurchaseOrder)
        .options(*PURCHASE_ORDER_LOAD_OPTIONS)
        .where(PurchaseOrder.id == purchase_order_id)
    )
    po = result.scalar_one_or_none()
    if not po:
        raise PurchaseOrderNotFound()
    return po
