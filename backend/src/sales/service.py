from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.catalog.models import Item
from src.exceptions import ConflictException
from src.inventory import service as inventory_service
from src.ledger import service as ledger_service
from src.pagination import PaginatedResponse, PaginationParams
from src.parties import service as parties_service
from src.parties.constants import PartyRole
from src.sales.exceptions import InvalidSalesOrderItem
from src.sales.models import SalesOrder, SalesOrderLine, SalesOrderLineLot
from src.sales.schemas import SalesOrderCreate, SalesOrderRead
from src.sales.utils import money


async def create_sales_order(db: AsyncSession, payload: SalesOrderCreate) -> SalesOrder:
    # party_id/order_date/lines all come from the request body, so this validation is
    # done here rather than via Depends() — same reasoning as purchasing.service.
    customer = await parties_service.get_active_party(db, payload.party_id)
    # A local vendor is a legitimate buyer of surplus stock too — no separate role needed.
    parties_service.ensure_any_role(customer, (PartyRole.CUSTOMER, PartyRole.LOCAL_VENDOR))

    requested_item_ids = [line.item_id for line in payload.lines]
    if len(set(requested_item_ids)) != len(requested_item_ids):
        raise InvalidSalesOrderItem("Each item may appear at most once per sales order — increase its qty instead")

    known_item_ids = set(
        (
            await db.scalars(
                select(Item.id).where(Item.id.in_(requested_item_ids), Item.is_active.is_(True))
            )
        ).all()
    )
    if missing := set(requested_item_ids) - known_item_ids:
        raise InvalidSalesOrderItem(f"Unknown or inactive item id(s): {sorted(missing)}")

    lines: list[SalesOrderLine] = []
    total_pkr = Decimal(0)
    for line_in in payload.lines:
        consumptions = await inventory_service.consume_stock_fifo(
            db,
            item_id=line_in.item_id,
            qty_needed=line_in.qty,
            movement_date=payload.order_date,
        )
        lines.append(
            SalesOrderLine(
                item_id=line_in.item_id,
                qty=line_in.qty,
                rate_pkr=line_in.rate_pkr,
                consumptions=[
                    SalesOrderLineLot(
                        stock_lot_id=c.stock_lot_id,
                        qty_consumed=c.qty_consumed,
                        unit_cost_pkr=c.unit_cost_pkr,
                    )
                    for c in consumptions
                ],
            )
        )
        # Same amount_pkr formula as SalesOrderLineRead, so the response total and the
        # ledger debit posted below can never disagree.
        total_pkr += money(line_in.qty * line_in.rate_pkr)
    total_pkr = money(total_pkr)

    # Lines are passed through the relationship, not inserted standalone, so so.lines
    # (and each line's .consumptions) stay populated through flush()/commit()
    # (expire_on_commit=False) without a lazy load.
    so = SalesOrder(party_id=customer.id, order_date=payload.order_date, lines=lines)
    db.add(so)
    await db.flush()  # assigns so.id, needed by the ledger reference below

    await ledger_service.post_entry(
        db,
        entry_date=payload.order_date,
        account="Accounts Receivable",
        debit=total_pkr,  # debit increases receivable — mirrors purchasing's credit-increases-payable
        reference_type="sales_order",
        reference_id=so.id,
        party_id=customer.id,
    )

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictException("Sales order could not be saved") from exc

    return so


async def list_sales_orders(db: AsyncSession, pagination: PaginationParams) -> PaginatedResponse[SalesOrderRead]:
    offset = (pagination.page - 1) * pagination.page_size

    total = await db.scalar(select(func.count()).select_from(SalesOrder))
    result = await db.execute(
        select(SalesOrder)
        .options(selectinload(SalesOrder.lines).selectinload(SalesOrderLine.consumptions))
        .order_by(SalesOrder.order_date.desc(), SalesOrder.id.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    items = result.scalars().all()

    return PaginatedResponse[SalesOrderRead](
        items=items,
        total=total or 0,
        page=pagination.page,
        page_size=pagination.page_size,
    )
