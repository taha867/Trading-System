from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database import get_db
from src.purchasing.exceptions import PurchaseOrderNotFound
from src.purchasing.models import PurchaseOrder


async def valid_purchase_order(purchase_order_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> PurchaseOrder:
    # select().options(selectinload(...)), not db.get() — Session.get() silently
    # ignores loader options when it serves the object from the identity map.
    result = await db.execute(
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.lines))
        .where(PurchaseOrder.id == purchase_order_id)
    )
    po = result.scalar_one_or_none()
    if not po:
        raise PurchaseOrderNotFound()
    return po
