from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.catalog.models import Item
from src.exceptions import ConflictException
from src.ledger import service as ledger_service
from src.pagination import PaginatedResponse, PaginationParams
from src.parties import service as parties_service
from src.parties.constants import PartyRole
from src.purchasing.exceptions import (
    ExchangeRateMissingForDate,
    InvalidPurchaseOrderItem,
)
from src.purchasing.models import ExchangeRate, PurchaseOrder, PurchaseOrderLine
from src.purchasing.schemas import PurchaseOrderCreate, PurchaseOrderRead
from src.purchasing.utils import money


async def create_purchase_order(db: AsyncSession, payload: PurchaseOrderCreate) -> PurchaseOrder:
    # party_id/order_date/lines all come from the request body, so this validation
    # is done here rather than via a FastAPI Depends() chain (a bare scalar
    # sub-dependency parameter resolves as a query param, not a body field).
    vendor = await parties_service.get_active_party(db, payload.party_id)
    # Exact-match role check, not ensure_any_role: source and the vendor's role must
    # agree — a china/local mismatch against what the vendor actually is should hard-fail,
    # not soft-match against either role.
    required_role = PartyRole.CHINA_VENDOR if payload.source == "china" else PartyRole.LOCAL_VENDOR
    parties_service.ensure_role(vendor, required_role)

    rate_row = None
    if payload.source == "china":
        rate_row = await db.scalar(
            select(ExchangeRate).where(
                ExchangeRate.rate_date == payload.order_date,
                ExchangeRate.is_active.is_(True),
            )
        )
        if rate_row is None:
            raise ExchangeRateMissingForDate()

    requested_item_ids = {line.item_id for line in payload.lines}
    known_item_ids = set(
        (
            await db.scalars(
                select(Item.id).where(Item.id.in_(requested_item_ids), Item.is_active.is_(True))
            )
        ).all()
    )
    if missing := requested_item_ids - known_item_ids:
        raise InvalidPurchaseOrderItem(f"Unknown or inactive item id(s): {sorted(missing)}")

    lines: list[PurchaseOrderLine] = []
    total_pkr = Decimal(0)
    for line in payload.lines:
        if payload.source == "china":
            rate_pkr = money(line.rate_rmb * rate_row.rate)
            po_line = PurchaseOrderLine(item_id=line.item_id, qty=line.qty, rate_rmb=line.rate_rmb, rate_pkr=rate_pkr)
        else:
            # No freight to allocate for a local pickup — landed cost is the quoted PKR
            # rate itself, set here instead of by cargo.service.create_shipment. Both
            # fields get the money()-rounded value, not the raw client input, so a
            # response never disagrees with what a subsequent GET reads back from the
            # Numeric(12,2) column.
            rate_pkr = money(line.rate_pkr)
            po_line = PurchaseOrderLine(
                item_id=line.item_id, qty=line.qty, rate_rmb=None, rate_pkr=rate_pkr, landed_cost_pkr=rate_pkr
            )
        lines.append(po_line)
        # Same amount_pkr formula as PurchaseOrderLineRead, so the response total and
        # the ledger credit posted below can never disagree.
        total_pkr += money(line.qty * rate_pkr)
    total_pkr = money(total_pkr)

    # Lines are passed through the relationship (not inserted standalone with an
    # explicit purchase_order_id) so po.lines stays loaded through flush()/commit()
    # (expire_on_commit=False) without a lazy load or an extra refresh round trip.
    po = PurchaseOrder(
        party_id=vendor.id,
        order_date=payload.order_date,
        source=payload.source,
        # Local orders skip the cargo step entirely — starting in "allocated" (rather
        # than "draft") reuses cargo.service.create_shipment's existing status=="draft"
        # gate (hardened to also check source == "local" explicitly) to keep them from
        # ever being attached to a shipment. See phase-5-backend.md §2.5.
        status="allocated" if payload.source == "local" else "draft",
        lines=lines,
    )
    db.add(po)
    await db.flush()  # assigns po.id, needed by the ledger reference below

    await ledger_service.post_entry(
        db,
        entry_date=payload.order_date,
        account="Accounts Payable",
        credit=total_pkr,  # credit increases payable — see spec §0 decision 2
        reference_type="purchase_order",
        reference_id=po.id,
        party_id=vendor.id,
    )

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise ConflictException("Purchase order could not be saved") from exc

    return po


async def list_purchase_orders(db: AsyncSession, pagination: PaginationParams) -> PaginatedResponse[PurchaseOrderRead]:
    offset = (pagination.page - 1) * pagination.page_size

    total = await db.scalar(select(func.count()).select_from(PurchaseOrder))
    result = await db.execute(
        select(PurchaseOrder)
        .options(selectinload(PurchaseOrder.lines))
        .order_by(PurchaseOrder.id)
        .offset(offset)
        .limit(pagination.page_size)
    )
    items = result.scalars().all()

    return PaginatedResponse[PurchaseOrderRead](
        items=items,
        total=total or 0,
        page=pagination.page,
        page_size=pagination.page_size,
    )
