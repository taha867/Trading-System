from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.cargo.exceptions import CargoShipmentNotFound
from src.cargo.models import CargoShipment
from src.database import get_db


async def valid_cargo_shipment(cargo_shipment_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> CargoShipment:
    # select().options(selectinload(...)), not db.get() — Session.get() silently
    # ignores loader options when it serves the object from the identity map.
    result = await db.execute(
        select(CargoShipment)
        .options(selectinload(CargoShipment.allocations))
        .where(CargoShipment.id == cargo_shipment_id)
    )
    shipment = result.scalar_one_or_none()
    if not shipment:
        raise CargoShipmentNotFound()
    return shipment
