from datetime import date
from decimal import Decimal

from sqlalchemy import exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, joinedload

from src.cargo.models import CargoAllocation, CargoShipment
from src.catalog.models import Item
from src.exceptions import ConflictException
from src.inventory.models import StockLot
from src.ledger import service as ledger_service
from src.ledger.models import LedgerEntry
from src.pagination import PaginationParams
from src.sorting import SortDirection, date_ordering
from src.parties import service as parties_service
from src.parties.constants import PartyRole
from src.purchasing.constants import MAX_INVOICE_NUMBER_LOOKUP_IDS, MAX_INVOICE_OPTIONS
from src.purchasing.dependencies import PURCHASE_ORDER_LOAD_OPTIONS
from src.purchasing.exceptions import (
    ExchangeRateMissingForDate,
    InvalidPurchaseFilter,
    InvalidPurchaseOrderItem,
)
from src.purchasing.models import ExchangeRate, PurchaseLogException, PurchaseOrder, PurchaseOrderLine
from src.purchasing.schemas import (
    InvoiceNumberRead,
    InvoiceOptionRead,
    PurchaseLogExceptionListRead,
    PurchaseOrderCreate,
    PurchaseOrderDetailRead,
    PurchaseOrderLineDetailRead,
    PurchaseOrderLineRead,
    PurchaseOrderListRead,
    PurchaseOrderRead,
)
from src.purchasing.utils import escape_like, money


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
        invoice_number=payload.invoice_number,
        # Local orders skip the cargo step entirely — starting in "allocated" (rather
        # than "draft") reuses cargo.service.create_shipment's existing status=="draft"
        # gate (hardened to also check source == "local" explicitly) to keep them from
        # ever being attached to a shipment. See phase-5-backend.md §2.5.
        status="allocated" if payload.source in ("local", "mohsin") else "draft",
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

    # po.lines itself survives commit fine (expire_on_commit=False), but each
    # line's `item` relationship (needed for PurchaseOrderLineRead's embedded
    # sku/model/category) was never touched, only item_id was set — re-fetch
    # with the same eager-load chain every other read path uses.
    result = await db.execute(select(PurchaseOrder).options(*PURCHASE_ORDER_LOAD_OPTIONS).where(PurchaseOrder.id == po.id))
    return result.unique().scalar_one()


def _validate_date_range(date_from: date | None, date_to: date | None) -> None:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise InvalidPurchaseFilter("date_from must be on or before date_to")


def _order_filter_clauses(
    *,
    search: str | None,
    invoice_number: str | None,
    party_id: int | None,
    source: str | None,
    status: str | None,
    date_from: date | None,
    date_to: date | None,
    item_id: int | None,
) -> list:
    """WHERE clauses over PurchaseOrder, shared by the count, both totals and the page query so the
    summary bar can never disagree with the rows (same idea as sales.service._order_filter_clauses)."""
    _validate_date_range(date_from, date_to)

    clauses = []
    if invoice_number is not None and invoice_number.strip():
        # Exact match — what the invoice dropdown sends once one is picked ("5" must not also
        # return invoices 35, 541 and 25, which the contains-style `search` would).
        clauses.append(PurchaseOrder.invoice_number == invoice_number.strip())
    if party_id is not None:
        clauses.append(PurchaseOrder.party_id == party_id)
    if source is not None:
        clauses.append(PurchaseOrder.source == source)
    if status is not None:
        clauses.append(PurchaseOrder.status == status)
    if date_from is not None:
        clauses.append(PurchaseOrder.order_date >= date_from)
    if date_to is not None:
        clauses.append(PurchaseOrder.order_date <= date_to)
    if item_id is not None:
        # EXISTS over an ALIASED line table: the totals queries already have PurchaseOrderLine in
        # their FROM, and an un-aliased subquery would auto-correlate to it and stop meaning
        # "this order has a line for item_id". EXISTS (not a join) also keeps each order once.
        line = aliased(PurchaseOrderLine)
        clauses.append(exists().where(line.purchase_order_id == PurchaseOrder.id, line.item_id == item_id))
    if search is not None and search.strip():
        text = search.strip()
        contains = PurchaseOrder.invoice_number.ilike(f"%{escape_like(text)}%", escape="\\")
        # All-digits input could be a "#57" order id as well as part of an invoice number.
        # The length cap keeps the int() inside Postgres' integer range.
        if text.isascii() and text.isdigit() and len(text) <= 9:
            clauses.append(or_(PurchaseOrder.id == int(text), contains))
        else:
            clauses.append(contains)
    return clauses


async def list_purchase_orders(
    db: AsyncSession,
    pagination: PaginationParams,
    *,
    search: str | None = None,
    invoice_number: str | None = None,
    party_id: int | None = None,
    source: str | None = None,
    status: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    item_id: int | None = None,
    sort: SortDirection = "newest",
) -> PurchaseOrderListRead:
    offset = (pagination.page - 1) * pagination.page_size
    clauses = _order_filter_clauses(
        search=search,
        invoice_number=invoice_number,
        party_id=party_id,
        source=source,
        status=status,
        date_from=date_from,
        date_to=date_to,
        item_id=item_id,
    )

    total = await db.scalar(select(func.count()).select_from(PurchaseOrder).where(*clauses))

    # Same filters, no offset/limit — the totals have to cover every matching order, not just the
    # page being rendered. One aggregate over the lines (never joined to anything else, so a line
    # can't be counted twice): PKR is every line, RMB is only the lines that were priced in RMB.
    total_pkr, total_rmb = (
        await db.execute(
            select(
                func.coalesce(func.sum(PurchaseOrderLine.qty * PurchaseOrderLine.rate_pkr), 0),
                func.coalesce(func.sum(PurchaseOrderLine.qty * PurchaseOrderLine.rate_rmb), 0),
            )
            .select_from(PurchaseOrderLine)
            .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderLine.purchase_order_id)
            .where(*clauses)
        )
    ).one()

    result = await db.execute(
        select(PurchaseOrder)
        .options(*PURCHASE_ORDER_LOAD_OPTIONS)
        .where(*clauses)
        .order_by(*date_ordering(PurchaseOrder.order_date, PurchaseOrder.id, sort))
        .offset(offset)
        .limit(pagination.page_size)
    )
    items = result.unique().scalars().all()

    return PurchaseOrderListRead(
        items=items,
        total=total or 0,
        page=pagination.page,
        page_size=pagination.page_size,
        total_amount_pkr=money(total_pkr),
        total_rmb=money(total_rmb),
    )


async def get_purchase_order_detail(db: AsyncSession, purchase_order: PurchaseOrder) -> PurchaseOrderDetailRead:
    """The order plus the ledger row it posted and, per line, what happened next (received into stock,
    allocated freight). Read-only. Lots and allocations are read by line id in one query each — not
    via model relationships — so purchasing.models never has to import inventory/cargo models."""
    entries = (
        await db.scalars(
            select(LedgerEntry)
            .where(LedgerEntry.reference_type == "purchase_order", LedgerEntry.reference_id == purchase_order.id)
            .order_by(LedgerEntry.entry_date, LedgerEntry.id)
        )
    ).all()

    line_ids = [line.id for line in purchase_order.lines]
    lots = {
        lot.purchase_order_line_id: lot
        for lot in (await db.scalars(select(StockLot).where(StockLot.purchase_order_line_id.in_(line_ids)))).all()
    }
    allocations = {
        allocation.purchase_order_line_id: (allocation, shipment)
        for allocation, shipment in (
            await db.execute(
                select(CargoAllocation, CargoShipment)
                .join(CargoShipment, CargoShipment.id == CargoAllocation.cargo_shipment_id)
                .where(CargoAllocation.purchase_order_line_id.in_(line_ids))
            )
        ).all()
    }

    base = PurchaseOrderRead.model_validate(purchase_order)
    detail_lines = []
    for line in base.lines:
        lot = lots.get(line.id)
        allocation, shipment = allocations.get(line.id, (None, None))
        detail_lines.append(
            PurchaseOrderLineDetailRead(
                **{name: getattr(line, name) for name in PurchaseOrderLineRead.model_fields},
                stock_lot_id=lot.id if lot else None,
                received_date=lot.received_date if lot else None,
                qty_received=lot.qty_received if lot else None,
                qty_remaining=lot.qty_remaining if lot else None,
                cargo_shipment_id=shipment.id if shipment else None,
                cargo_shipment_date=shipment.shipment_date if shipment else None,
                allocated_cost_pkr=allocation.allocated_cost_pkr if allocation else None,
            )
        )
    fields = {name: getattr(base, name) for name in PurchaseOrderRead.model_fields if name != "lines"}
    return PurchaseOrderDetailRead(**fields, lines=detail_lines, ledger_entries=entries)


async def get_invoice_numbers(db: AsyncSession, ids: list[int]) -> list[InvoiceNumberRead]:
    """Batched id -> invoice number lookup for other screens (the vendor statement lists purchase
    orders by id only). Lives here, not in parties/, because parties/ never imports purchasing/."""
    if len(ids) > MAX_INVOICE_NUMBER_LOOKUP_IDS:
        raise InvalidPurchaseFilter(f"At most {MAX_INVOICE_NUMBER_LOOKUP_IDS} ids per lookup")
    if not ids:
        return []
    rows = (await db.execute(select(PurchaseOrder.id, PurchaseOrder.invoice_number).where(PurchaseOrder.id.in_(ids)))).all()
    return [InvoiceNumberRead(id=order_id, invoice_number=invoice_number) for order_id, invoice_number in rows]


async def list_invoice_options(db: AsyncSession, search: str | None = None) -> list[InvoiceOptionRead]:
    """Distinct invoice numbers for the Purchase Orders dropdown — most recently used first, narrowed by
    what the user types (contains, case-insensitive). Capped: the dropdown is a picker, not a report."""
    stmt = select(PurchaseOrder.invoice_number, func.count(PurchaseOrder.id)).where(
        PurchaseOrder.invoice_number.is_not(None), PurchaseOrder.invoice_number != ""
    )
    if search is not None and search.strip():
        stmt = stmt.where(PurchaseOrder.invoice_number.ilike(f"%{escape_like(search.strip())}%", escape="\\"))
    rows = (
        await db.execute(
            stmt.group_by(PurchaseOrder.invoice_number)
            .order_by(func.max(PurchaseOrder.order_date).desc(), PurchaseOrder.invoice_number)
            .limit(MAX_INVOICE_OPTIONS)
        )
    ).all()
    return [InvoiceOptionRead(invoice_number=number, order_count=count) for number, count in rows]


async def list_purchase_log_exceptions(
    db: AsyncSession,
    pagination: PaginationParams,
    *,
    search: str | None = None,
    party_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    sort: SortDirection = "newest",
) -> PurchaseLogExceptionListRead:
    _validate_date_range(date_from, date_to)
    offset = (pagination.page - 1) * pagination.page_size

    filters = []
    if party_id is not None:
        filters.append(PurchaseLogException.party_id == party_id)
    if date_from is not None:
        filters.append(PurchaseLogException.entry_date >= date_from)
    if date_to is not None:
        filters.append(PurchaseLogException.entry_date <= date_to)
    if search is not None and search.strip():
        pattern = f"%{escape_like(search.strip())}%"
        filters.append(
            or_(
                PurchaseLogException.invoice_number.ilike(pattern, escape="\\"),
                PurchaseLogException.note.ilike(pattern, escape="\\"),
            )
        )

    total = await db.scalar(select(func.count()).select_from(PurchaseLogException).where(*filters))
    total_amount = await db.scalar(
        select(func.coalesce(func.sum(PurchaseLogException.amount_pkr), 0)).where(*filters)
    )
    result = await db.execute(
        select(PurchaseLogException)
        .options(joinedload(PurchaseLogException.party))
        .where(*filters)
        .order_by(*date_ordering(PurchaseLogException.entry_date, PurchaseLogException.id, sort))
        .offset(offset)
        .limit(pagination.page_size)
    )
    items = result.scalars().all()

    return PurchaseLogExceptionListRead(
        items=items,
        total=total or 0,
        page=pagination.page,
        page_size=pagination.page_size,
        total_amount_pkr=money(total_amount),
    )
