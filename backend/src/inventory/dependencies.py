from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.catalog.models import Item
from src.database import get_db
from src.inventory.exceptions import StockLotNotFound
from src.inventory.models import StockLot, StockMovement

# Reused everywhere a StockLot is loaded — StockLotRead's item_sku/item_variant/
# model_name/category_name properties need this whole chain eagerly loaded
# (lazy="raise" on every hop) or serialization blows up.
STOCK_LOT_LOAD_OPTIONS = (
    joinedload(StockLot.item).joinedload(Item.model),
    joinedload(StockLot.item).joinedload(Item.category),
)

# Same reasoning, one hop further — StockMovementRead's embedded fields read
# through movement.stock_lot.item.model/category.
STOCK_MOVEMENT_LOAD_OPTIONS = (
    joinedload(StockMovement.stock_lot).joinedload(StockLot.item).joinedload(Item.model),
    joinedload(StockMovement.stock_lot).joinedload(StockLot.item).joinedload(Item.category),
)


async def valid_stock_lot(stock_lot_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> StockLot:
    # select().options(...), not db.get() — Session.get() silently ignores loader
    # options when it serves the object from the identity map. StockLot's `item`
    # relationship (added for StockLotRead's embedded display fields) is
    # lazy="raise", so this must eager-load it explicitly.
    result = await db.execute(
        select(StockLot).options(*STOCK_LOT_LOAD_OPTIONS).where(StockLot.id == stock_lot_id)
    )
    lot = result.unique().scalar_one_or_none()
    if not lot:
        raise StockLotNotFound()
    return lot
