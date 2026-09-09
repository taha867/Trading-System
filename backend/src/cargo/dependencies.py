from typing import Annotated

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.cargo.exceptions import CargoShipmentNotFound
from src.cargo.models import CargoAllocation, CargoShipment
from src.catalog.models import Item
from src.database import get_db
from src.purchasing.models import PurchaseOrderLine

# Reused everywhere a CargoShipment's allocations are loaded — CargoAllocationRead's
# item_sku/item_variant/model_name/category_name properties need this whole chain
# eagerly loaded (lazy="raise" on every hop) or serialization blows up.
CARGO_SHIPMENT_LOAD_OPTIONS = (
    selectinload(CargoShipment.allocations)
    .joinedload(CargoAllocation.purchase_order_line)
    .joinedload(PurchaseOrderLine.item)
    .joinedload(Item.model),
    selectinload(CargoShipment.allocations)
    .joinedload(CargoAllocation.purchase_order_line)
    .joinedload(PurchaseOrderLine.item)
    .joinedload(Item.category),
)


async def valid_cargo_shipment(cargo_shipment_id: int, db: Annotated[AsyncSession, Depends(get_db)]) -> CargoShipment:
    # select().options(selectinload(...)), not db.get() — Session.get() silently
    # ignores loader options when it serves the object from the identity map.
    result = await db.execute(
        select(CargoShipment)
        .options(*CARGO_SHIPMENT_LOAD_OPTIONS)
        .where(CargoShipment.id == cargo_shipment_id)
    )
    shipment = result.scalar_one_or_none()
    if not shipment:
        raise CargoShipmentNotFound()
    return shipment
