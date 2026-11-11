from datetime import date
from decimal import Decimal
from typing import NamedTuple, Sequence

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.dates import validate_date_range
from src.catalog.models import Item, ItemCompatibleModel, Model
from src.exceptions import ConflictException
from src.inventory.dependencies import (
    STOCK_LOT_LOAD_OPTIONS,
    STOCK_MOVEMENT_LOAD_OPTIONS,
)
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
    FittingItemRead,
    ItemAvailabilityRead,
    StockLotDamageCreate,
    StockLotListRead,
    StockLotReceiveCreate,
    StockMovementCreate,
    StockMovementListRead,
)
from src.inventory.utils import money
from src.ledger import service as ledger_service
from src.pagination import PaginationParams
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

    # lot's own columns survive commit fine, but `item` (needed for StockLotRead's
    # embedded sku/model/category) was never touched — re-fetch with the same
    # eager-load chain every other read path uses.
    result = await db.execute(select(StockLot).options(*STOCK_LOT_LOAD_OPTIONS).where(StockLot.id == lot.id))
    return result.unique().scalar_one()


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


async def mark_stock_lot_damaged(db: AsyncSession, payload: StockLotDamageCreate) -> StockMovement:
    lot = await db.get(StockLot, payload.stock_lot_id)
    if not lot:
        raise StockLotNotFound()
    if payload.qty > lot.qty_remaining:
        raise InvalidAdjustment(
            f"Cannot mark {payload.qty} damaged — only {lot.qty_remaining} remaining on this lot"
        )

    lot.qty_remaining -= payload.qty
    movement = StockMovement(
        stock_lot_id=lot.id,
        movement_type="damaged",
        qty_delta=-payload.qty,
        reason=payload.reason,
        movement_date=payload.movement_date,
    )
    db.add(movement)

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictException("Damage record could not be saved") from exc

    # movement's own columns survive commit fine, but `stock_lot` (needed for
    # StockMovementRead's embedded sku/model/category) was never touched —
    # re-fetch with the same eager-load chain every other read path uses.
    result = await db.execute(
        select(StockMovement).options(*STOCK_MOVEMENT_LOAD_OPTIONS).where(StockMovement.id == movement.id)
    )
    return result.unique().scalar_one()


class FifoConsumption(NamedTuple):
    stock_lot_id: int
    qty_consumed: Decimal
    unit_cost_pkr: Decimal


class LotView(NamedTuple):
    """The few lot fields the consumption plan needs - lets the plan be tested without a database."""

    id: int
    item_id: int
    qty_remaining: Decimal
    received_date: date
    landed_cost_pkr: Decimal


def plan_consumption(own_item_id: int, lots: Sequence[LotView], qty_needed: Decimal) -> list[FifoConsumption]:
    """Decide which lots a sale of `qty_needed` of `own_item_id` takes from.

    The item's own lots go first, oldest received first (id breaks ties). Only when they are used up does the
    sale continue with the lots of the items that also fit that phone, again oldest received first across all of
    them. Raises InsufficientStock when both together are not enough. Pure: no database, no side effects.
    """
    usable = [lot for lot in lots if lot.qty_remaining > 0]
    own = sorted((lot for lot in usable if lot.item_id == own_item_id), key=lambda lot: (lot.received_date, lot.id))
    fitting = sorted((lot for lot in usable if lot.item_id != own_item_id), key=lambda lot: (lot.received_date, lot.id))
    own_total = sum((lot.qty_remaining for lot in own), Decimal(0))
    fitting_total = sum((lot.qty_remaining for lot in fitting), Decimal(0))
    if own_total + fitting_total < qty_needed:
        raise InsufficientStock(
            f"Item {own_item_id}: need {qty_needed}, only {own_total} in this item"
            + (f" and {fitting_total} in items that also fit" if fitting_total else "")
        )
    plan: list[FifoConsumption] = []
    remaining = qty_needed
    for lot in [*own, *fitting]:
        if remaining <= 0:
            break
        taken = min(remaining, lot.qty_remaining)
        plan.append(FifoConsumption(lot.id, taken, lot.landed_cost_pkr))
        remaining -= taken
    return plan


async def fitting_item_ids(db: AsyncSession, item_id: int) -> list[int]:
    """Other active items that fit the same phone as `item_id`: same category and colour, and the item's primary
    phone is that item's primary phone or one of its compatible phones ("also fits")."""
    item = await db.get(Item, item_id)
    if item is None:
        return []
    variant = (item.variant or "").strip().upper()
    compatible_with_phone = select(ItemCompatibleModel.item_id).where(ItemCompatibleModel.model_id == item.model_id)
    rows = await db.scalars(
        select(Item.id).where(
            Item.is_active.is_(True),
            Item.id != item_id,
            Item.category_id == item.category_id,
            func.upper(func.coalesce(Item.variant, "")) == variant,
            or_(Item.model_id == item.model_id, Item.id.in_(compatible_with_phone)),
        )
    )
    return list(rows.all())


async def consume_stock_fifo(
    db: AsyncSession, *, item_id: int, qty_needed: Decimal, movement_date: date
) -> list[FifoConsumption]:
    """Take stock for a sale: the item's own lots first (oldest first), then - only when those run out - the lots of
    the items that also fit the same phone (oldest first). Costs are each lot's own landed cost."""
    candidate_item_ids = [item_id, *await fitting_item_ids(db, item_id)]
    # One locking query over every candidate lot, ordered by id: two concurrent sales lock rows in the same order,
    # so they queue instead of deadlocking (with_for_update is also what stops two sales taking the same pieces).
    lots = (
        await db.scalars(
            select(StockLot)
            .where(StockLot.item_id.in_(candidate_item_ids), StockLot.qty_remaining > 0)
            .order_by(StockLot.id)
            .with_for_update()
        )
    ).all()
    by_id = {lot.id: lot for lot in lots}
    plan = plan_consumption(
        item_id,
        [LotView(lot.id, lot.item_id, lot.qty_remaining, lot.received_date, lot.landed_cost_pkr) for lot in lots],
        qty_needed,
    )
    for taken in plan:
        lot = by_id[taken.stock_lot_id]
        lot.qty_remaining -= taken.qty_consumed
        db.add(
            StockMovement(
                stock_lot_id=lot.id,
                movement_type="sale",
                qty_delta=-taken.qty_consumed,
                reason=None,
                movement_date=movement_date,
            )
        )
    return plan


async def get_availability(db: AsyncSession, item_ids: list[int]) -> list[ItemAvailabilityRead]:
    """For each item: pieces in the item itself, and pieces in the other items that also fit its phone."""
    out: list[ItemAvailabilityRead] = []
    for item_id in dict.fromkeys(item_ids):
        fitting_ids = await fitting_item_ids(db, item_id)
        rows = (
            await db.execute(
                select(Item.id, Item.sku, func.coalesce(func.sum(StockLot.qty_remaining), 0))
                .join(StockLot, StockLot.item_id == Item.id, isouter=True)
                .where(Item.id.in_([item_id, *fitting_ids]))
                .group_by(Item.id, Item.sku)
            )
        ).all()
        qty_by_item = {row[0]: (row[1], Decimal(row[2])) for row in rows}
        fitting = [
            FittingItemRead(item_id=i, sku=qty_by_item[i][0], qty=qty_by_item[i][1])
            for i in fitting_ids
            if i in qty_by_item and qty_by_item[i][1] > 0
        ]
        out.append(
            ItemAvailabilityRead(
                item_id=item_id,
                own_qty=qty_by_item.get(item_id, ("", Decimal(0)))[1],
                fitting_qty=sum((f.qty for f in fitting), Decimal(0)),
                fitting=fitting,
            )
        )
    return out


async def list_stock_lots(
    db: AsyncSession,
    pagination: PaginationParams,
    item_id: int | None,
    include_depleted: bool,
    category_id: int | None = None,
    brand_id: int | None = None,
    model_id: int | None = None,
) -> StockLotListRead:
    offset = (pagination.page - 1) * pagination.page_size

    filters = []
    if item_id is not None:
        filters.append(StockLot.item_id == item_id)
    if not include_depleted:
        filters.append(StockLot.qty_remaining > 0)
    if category_id is not None:
        filters.append(Item.category_id == category_id)
    if model_id is not None:
        filters.append(Item.model_id == model_id)
    if brand_id is not None:
        filters.append(Model.brand_id == brand_id)

    # category_id/model_id only need Item; brand_id needs the further Item -> Model
    # hop — join both whenever either filter is in play so brand_id isn't a special case.
    needs_join = category_id is not None or model_id is not None or brand_id is not None

    count_stmt = select(func.count()).select_from(StockLot).where(*filters)
    # Same filters, no offset/limit — "how much stock is on hand" has to sum every
    # matching lot, not just the page being rendered.
    sum_stmt = select(
        func.coalesce(func.sum(StockLot.qty_remaining), 0),
        func.coalesce(func.sum(StockLot.qty_remaining * StockLot.landed_cost_pkr), 0),
    ).where(*filters)
    list_stmt = select(StockLot).options(*STOCK_LOT_LOAD_OPTIONS).where(*filters)
    if needs_join:
        count_stmt = count_stmt.join(Item, Item.id == StockLot.item_id).join(Model, Model.id == Item.model_id)
        sum_stmt = sum_stmt.join(Item, Item.id == StockLot.item_id).join(Model, Model.id == Item.model_id)
        list_stmt = list_stmt.join(Item, Item.id == StockLot.item_id).join(Model, Model.id == Item.model_id)

    total = await db.scalar(count_stmt)
    total_qty_remaining, total_value_remaining_pkr = (await db.execute(sum_stmt)).one()
    result = await db.execute(
        list_stmt.order_by(StockLot.item_id, StockLot.received_date, StockLot.id).offset(offset).limit(pagination.page_size)
    )
    items = result.unique().scalars().all()

    return StockLotListRead(
        items=items,
        total=total or 0,
        page=pagination.page,
        page_size=pagination.page_size,
        total_qty_remaining=total_qty_remaining,
        total_value_remaining_pkr=money(total_value_remaining_pkr),
    )


async def list_stock_movements(
    db: AsyncSession,
    pagination: PaginationParams,
    stock_lot_id: int | None,
    movement_type: str | None = None,
    category_id: int | None = None,
    brand_id: int | None = None,
    model_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> StockMovementListRead:
    offset = (pagination.page - 1) * pagination.page_size
    validate_date_range(date_from, date_to)

    filters = []
    if date_from is not None:
        filters.append(StockMovement.movement_date >= date_from)
    if date_to is not None:
        filters.append(StockMovement.movement_date <= date_to)
    if stock_lot_id is not None:
        filters.append(StockMovement.stock_lot_id == stock_lot_id)
    if movement_type is not None:
        filters.append(StockMovement.movement_type == movement_type)
    if category_id is not None:
        filters.append(Item.category_id == category_id)
    if model_id is not None:
        filters.append(Item.model_id == model_id)
    if brand_id is not None:
        filters.append(Model.brand_id == brand_id)

    # category_id/model_id only need Item; brand_id needs the further Item -> Model
    # hop — join both whenever either filter is in play, same reasoning as
    # list_stock_lots above.
    needs_join = category_id is not None or model_id is not None or brand_id is not None

    count_stmt = select(func.count()).select_from(StockMovement).where(*filters)
    # Same filters, no offset/limit — "how many units total" (the Damaged Stock
    # page's own summary) has to sum every matching row, not just the page
    # being rendered. qty_delta is negative for "damaged"/most adjustments, so
    # this sums the magnitude, not the signed value.
    total_qty_stmt = select(func.coalesce(func.sum(-StockMovement.qty_delta), 0)).where(*filters)
    list_stmt = select(StockMovement).options(*STOCK_MOVEMENT_LOAD_OPTIONS).where(*filters)
    if needs_join:
        count_stmt = count_stmt.join(StockLot, StockLot.id == StockMovement.stock_lot_id).join(
            Item, Item.id == StockLot.item_id
        ).join(Model, Model.id == Item.model_id)
        total_qty_stmt = total_qty_stmt.join(StockLot, StockLot.id == StockMovement.stock_lot_id).join(
            Item, Item.id == StockLot.item_id
        ).join(Model, Model.id == Item.model_id)
        list_stmt = list_stmt.join(StockLot, StockLot.id == StockMovement.stock_lot_id).join(
            Item, Item.id == StockLot.item_id
        ).join(Model, Model.id == Item.model_id)

    total = await db.scalar(count_stmt)
    total_qty = await db.scalar(total_qty_stmt)
    result = await db.execute(
        list_stmt.order_by(StockMovement.id.desc()).offset(offset).limit(pagination.page_size)
    )
    items = result.unique().scalars().all()

    return StockMovementListRead(
        items=items,
        total=total or 0,
        page=pagination.page,
        page_size=pagination.page_size,
        total_qty=money(total_qty or Decimal(0)),
    )
