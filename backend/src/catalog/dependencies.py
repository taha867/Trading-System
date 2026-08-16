from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.catalog import service
from src.catalog.models import Item
from src.database import get_db


async def valid_item(item_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> Item:
    return await service.get_item(db, item_id)
