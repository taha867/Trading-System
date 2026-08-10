from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.database import get_db
from src.inventory.exceptions import StockLotNotFound
from src.inventory.models import StockLot


async def valid_stock_lot(stock_lot_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> StockLot:
    # Plain db.get() is fine here (unlike valid_purchase_order/valid_cargo_shipment) —
    # StockLot has no relationship attributes to eager-load, so there's no lazy="raise"
    # trap to fall into.
    lot = await db.get(StockLot, stock_lot_id)
    if not lot:
        raise StockLotNotFound()
    return lot
