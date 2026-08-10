from datetime import date
from decimal import Decimal
from typing import NamedTuple

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.exceptions import ConflictException
from src.inventory.exceptions import (
    InsufficientStock,
    InvalidAdjustment,
    LineAlreadyReceived,
    LineNotAllocated,
    PurchaseOrderLineNotFound,
    StockLotNotFound,
)
from src.inventory.models import StockLot, StockMovement
from src.inventory.schemas import (
    StockLotRead,
    StockLotReceiveCreate,
    StockMovementCreate,
    StockMovementRead,
)
from src.inventory.utils import money
from src.ledger import service as ledger_service
from src.pagination import PaginatedResponse, PaginationParams
from src.purchasing.models import PurchaseOrder, PurchaseOrderLine


async def receive_purchase_order_line(db: AsyncSession, payload: StockLotReceiveCreate) -> StockLot:
    line = await db.get(PurchaseOrderLine, payload.purchase_order_line_id)
    if not line:
        raise PurchaseOrderLineNotFound()
    if line.landed_cost_pkr is None:
        raise LineNotAllocated()

    existing = await db.scalar(select(StockLot).where(StockLot.purchase_order_line_id == line.id))
    if existing:
        raise LineAlreadyReceived()

    lot = StockLot(
        purchase_order_line_id=line.id,
        item_id=line.item_id,
        qty_received=line.qty,
        qty_remaining=line.qty,
        landed_cost_pkr=line.landed_cost_pkr,
        received_date=payload.received_date,
    )
    db.add(lot)
    await db.flush()  # assigns lot.id, needed by the movement + ledger rows below

    db.add(
        StockMovement(
            stock_lot_id=lot.id,
            movement_type="receipt",
            qty_delta=lot.qty_received,
            reason=None,
            movement_date=payload.received_date,
        )
    )

    await ledger_service.post_entry(
        db,
        entry_date=payload.received_date,
        account="Inventory",
        debit=money(lot.qty_received * lot.landed_cost_pkr),
        reference_type="stock_lot",
        reference_id=lot.id,
    )

    # Flip the PO to "received" once every one of its lines has a lot — mirrors
    # cargo.service.create_shipment's whole-PO status flip to "allocated". `lot` is
    # already flushed, so this count query sees it within the same transaction.
    unreceived_count = await db.scalar(
        select(func.count())
        .select_from(PurchaseOrderLine)
        .outerjoin(StockLot, StockLot.purchase_order_line_id == PurchaseOrderLine.id)
        .where(PurchaseOrderLine.purchase_order_id == line.purchase_order_id, StockLot.id.is_(None))
    )
    if unreceived_count == 0:
        po = await db.get(PurchaseOrder, line.purchase_order_id)
        po.status = "received"

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictException("Stock lot could not be saved") from exc

    await db.refresh(lot)
    return lot


async def create_adjustment(db: AsyncSession, payload: StockMovementCreate) -> StockMovement:
    lot = await db.get(StockLot, payload.stock_lot_id)
    if not lot:
        raise StockLotNotFound()
    if payload.qty_delta == 0:
        raise InvalidAdjustment("Adjustment quantity must be non-zero")

    new_remaining = lot.qty_remaining + payload.qty_delta
    if new_remaining < 0 or new_remaining > lot.qty_received:
        raise InvalidAdjustment(
            f"Adjustment would put qty_remaining at {new_remaining}, outside [0, {lot.qty_received}]"
        )

    lot.qty_remaining = new_remaining
    movement = StockMovement(
        stock_lot_id=lot.id,
        movement_type="adjustment",
        qty_delta=payload.qty_delta,
        reason=payload.reason,
        movement_date=payload.movement_date,
    )
    db.add(movement)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictException("Adjustment could not be saved") from exc

    await db.refresh(movement)
    return movement


class FifoConsumption(NamedTuple):
    stock_lot_id: int
    qty_consumed: Decimal
    unit_cost_pkr: Decimal


async def consume_stock_fifo(
    db: AsyncSession, *, item_id: int, qty_needed: Decimal, movement_date: date
) -> list[FifoConsumption]:
    # Oldest lot first, same ordering list_stock_lots already uses. with_for_update()
    # is new to this codebase — the first place a service reads a *set* of rows and
    # mutates based on their aggregate value, so it's the first place a race between
    # two concurrent writers (two sales against the same low-stock item) is possible.
    lots = (
        await db.scalars(
            select(StockLot)
            .where(StockLot.item_id == item_id, StockLot.qty_remaining > 0)
            .order_by(StockLot.received_date, StockLot.id)
            .with_for_update()
        )
    ).all()

    available = sum((lot.qty_remaining for lot in lots), Decimal(0))
    if available < qty_needed:
        raise InsufficientStock(f"Item {item_id}: need {qty_needed}, only {available} in stock")

    consumptions: list[FifoConsumption] = []
    remaining_needed = qty_needed
    for lot in lots:
        if remaining_needed <= 0:
            break
        consumed = min(remaining_needed, lot.qty_remaining)
        lot.qty_remaining -= consumed
        db.add(
            StockMovement(
                stock_lot_id=lot.id,
                movement_type="sale",
                qty_delta=-consumed,
                reason=None,
                movement_date=movement_date,
            )
        )
        consumptions.append(FifoConsumption(lot.id, consumed, lot.landed_cost_pkr))
        remaining_needed -= consumed

    return consumptions


async def list_stock_lots(
    db: AsyncSession,
    pagination: PaginationParams,
    item_id: int | None,
    include_depleted: bool,
) -> PaginatedResponse[StockLotRead]:
    offset = (pagination.page - 1) * pagination.page_size

    filters = []
    if item_id is not None:
        filters.append(StockLot.item_id == item_id)
    if not include_depleted:
        filters.append(StockLot.qty_remaining > 0)

    total = await db.scalar(select(func.count()).select_from(StockLot).where(*filters))
    result = await db.execute(
        select(StockLot)
        .where(*filters)
        .order_by(StockLot.item_id, StockLot.received_date, StockLot.id)
        .offset(offset)
        .limit(pagination.page_size)
    )
    items = result.scalars().all()

    return PaginatedResponse[StockLotRead](
        items=items,
        total=total or 0,
        page=pagination.page,
        page_size=pagination.page_size,
    )


async def list_stock_movements(
    db: AsyncSession,
    pagination: PaginationParams,
    stock_lot_id: int | None,
) -> PaginatedResponse[StockMovementRead]:
    offset = (pagination.page - 1) * pagination.page_size

    filters = []
    if stock_lot_id is not None:
        filters.append(StockMovement.stock_lot_id == stock_lot_id)

    total = await db.scalar(select(func.count()).select_from(StockMovement).where(*filters))
    result = await db.execute(
        select(StockMovement)
        .where(*filters)
        .order_by(StockMovement.id)
        .offset(offset)
        .limit(pagination.page_size)
    )
    items = result.scalars().all()

    return PaginatedResponse[StockMovementRead](
        items=items,
        total=total or 0,
        page=pagination.page,
        page_size=pagination.page_size,
    )
