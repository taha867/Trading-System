from datetime import date
from decimal import Decimal

from sqlalchemy import exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, joinedload

from src.catalog.models import Item
from src.exceptions import ConflictException
from src.inventory import service as inventory_service
from src.ledger import service as ledger_service
from src.ledger.models import LedgerEntry
from src.pagination import PaginationParams
from src.parties import service as parties_service
from src.parties.constants import PartyRole
from src.sales.constants import MAX_INVOICE_NUMBER_LOOKUP_IDS, MAX_INVOICE_OPTIONS
from src.sales.dependencies import SALES_ORDER_LOAD_OPTIONS
from src.sales.exceptions import InvalidSalesFilter, InvalidSalesOrderItem
from src.sales.models import SalesLogException, SalesOrder, SalesOrderLine, SalesOrderLineLot
from src.sales.schemas import (
    InvoiceNumberRead,
    InvoiceOptionRead,
    SalesLogExceptionKindTotalRead,
    SalesLogExceptionListRead,
    SalesOrderCreate,
    SalesOrderDetailRead,
    SalesOrderListRead,
    SalesOrderRead,
)
from src.sales.utils import escape_like, money


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
    so = SalesOrder(
        party_id=customer.id, order_date=payload.order_date, invoice_number=payload.invoice_number, lines=lines
    )
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

    # so.lines/.consumptions survive commit fine (expire_on_commit=False), but each
    # line's `item` relationship (needed for SalesOrderLineRead's embedded
    # sku/model/category) was never touched, only item_id was set — re-fetch
    # with the same eager-load chain every other read path uses.
    result = await db.execute(select(SalesOrder).options(*SALES_ORDER_LOAD_OPTIONS).where(SalesOrder.id == so.id))
    return result.unique().scalar_one()


def _validate_date_range(date_from: date | None, date_to: date | None) -> None:
    if date_from is not None and date_to is not None and date_from > date_to:
        raise InvalidSalesFilter("date_from must be on or before date_to")


def _order_filter_clauses(
    *,
    search: str | None,
    invoice_number: str | None,
    party_id: int | None,
    date_from: date | None,
    date_to: date | None,
    item_id: int | None,
) -> list:
    """WHERE clauses over SalesOrder, shared by the count, both totals and the page query so the
    summary bar can never disagree with the rows (same idea as inventory.list_stock_lots)."""
    _validate_date_range(date_from, date_to)

    clauses = []
    if invoice_number is not None and invoice_number.strip():
        # Exact match — what the Sales Orders invoice dropdown sends once one is picked ("5" must
        # not also return invoices 35, 541 and 25, which the contains-style `search` would).
        clauses.append(SalesOrder.invoice_number == invoice_number.strip())
    if party_id is not None:
        clauses.append(SalesOrder.party_id == party_id)
    if date_from is not None:
        clauses.append(SalesOrder.order_date >= date_from)
    if date_to is not None:
        clauses.append(SalesOrder.order_date <= date_to)
    if item_id is not None:
        # EXISTS over an ALIASED line table: the totals queries already have SalesOrderLine in
        # their FROM, and an un-aliased subquery would auto-correlate to it and stop meaning
        # "this order has a line for item_id". EXISTS (not a join) also keeps each sale once.
        line = aliased(SalesOrderLine)
        clauses.append(exists().where(line.sales_order_id == SalesOrder.id, line.item_id == item_id))
    if search is not None and search.strip():
        text = search.strip()
        contains = SalesOrder.invoice_number.ilike(f"%{escape_like(text)}%", escape="\\")
        # All-digits input could be a "#57" order id as well as part of an invoice number.
        # The length cap keeps the int() inside Postgres' integer range.
        if text.isascii() and text.isdigit() and len(text) <= 9:
            clauses.append(or_(SalesOrder.id == int(text), contains))
        else:
            clauses.append(contains)
    return clauses


async def list_sales_orders(
    db: AsyncSession,
    pagination: PaginationParams,
    *,
    search: str | None = None,
    invoice_number: str | None = None,
    party_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    item_id: int | None = None,
) -> SalesOrderListRead:
    offset = (pagination.page - 1) * pagination.page_size
    clauses = _order_filter_clauses(
        search=search,
        invoice_number=invoice_number,
        party_id=party_id,
        date_from=date_from,
        date_to=date_to,
        item_id=item_id,
    )

    total = await db.scalar(select(func.count()).select_from(SalesOrder).where(*clauses))

    # Same filters, no offset/limit — "total sales" has to cover every matching sale, not just the
    # page being rendered. Revenue and cost are SEPARATE aggregates on purpose: joining the lot rows
    # into the revenue query would multiply qty * rate_pkr by the number of lots a line drew from.
    sales_total = await db.scalar(
        select(func.coalesce(func.sum(SalesOrderLine.qty * SalesOrderLine.rate_pkr), 0))
        .select_from(SalesOrderLine)
        .join(SalesOrder, SalesOrder.id == SalesOrderLine.sales_order_id)
        .where(*clauses)
    )
    cost_total = await db.scalar(
        select(func.coalesce(func.sum(SalesOrderLineLot.qty_consumed * SalesOrderLineLot.unit_cost_pkr), 0))
        .select_from(SalesOrderLineLot)
        .join(SalesOrderLine, SalesOrderLine.id == SalesOrderLineLot.sales_order_line_id)
        .join(SalesOrder, SalesOrder.id == SalesOrderLine.sales_order_id)
        .where(*clauses)
    )

    result = await db.execute(
        select(SalesOrder)
        .options(*SALES_ORDER_LOAD_OPTIONS)
        .where(*clauses)
        .order_by(SalesOrder.order_date.desc(), SalesOrder.id.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    items = result.unique().scalars().all()

    return SalesOrderListRead(
        items=items,
        total=total or 0,
        page=pagination.page,
        page_size=pagination.page_size,
        total_sales_pkr=money(sales_total),
        total_margin_pkr=money(sales_total - cost_total),
    )


async def get_sales_order_detail(db: AsyncSession, sales_order: SalesOrder) -> SalesOrderDetailRead:
    """The sale plus the LedgerEntry rows it posted. Read-only."""
    entries = (
        await db.scalars(
            select(LedgerEntry)
            .where(LedgerEntry.reference_type == "sales_order", LedgerEntry.reference_id == sales_order.id)
            .order_by(LedgerEntry.entry_date, LedgerEntry.id)
        )
    ).all()
    base = SalesOrderRead.model_validate(sales_order)
    return SalesOrderDetailRead(
        **{name: getattr(base, name) for name in SalesOrderRead.model_fields}, ledger_entries=entries
    )


async def get_invoice_numbers(db: AsyncSession, ids: list[int]) -> list[InvoiceNumberRead]:
    """Batched id -> invoice number lookup for other screens (the customer statement lists
    sales by id only). Lives here, not in parties/, because parties/ never imports sales/."""
    if len(ids) > MAX_INVOICE_NUMBER_LOOKUP_IDS:
        raise InvalidSalesFilter(f"At most {MAX_INVOICE_NUMBER_LOOKUP_IDS} ids per lookup")
    if not ids:
        return []
    rows = (await db.execute(select(SalesOrder.id, SalesOrder.invoice_number).where(SalesOrder.id.in_(ids)))).all()
    return [InvoiceNumberRead(id=order_id, invoice_number=invoice_number) for order_id, invoice_number in rows]


async def list_invoice_options(db: AsyncSession, search: str | None = None) -> list[InvoiceOptionRead]:
    """Distinct invoice numbers for the Sales Orders dropdown — most recently used first, narrowed by
    what the user types (contains, case-insensitive). Capped: the dropdown is a picker, not a report."""
    stmt = select(SalesOrder.invoice_number, func.count(SalesOrder.id)).where(
        SalesOrder.invoice_number.is_not(None), SalesOrder.invoice_number != ""
    )
    if search is not None and search.strip():
        stmt = stmt.where(SalesOrder.invoice_number.ilike(f"%{escape_like(search.strip())}%", escape="\\"))
    rows = (
        await db.execute(
            stmt.group_by(SalesOrder.invoice_number)
            .order_by(func.max(SalesOrder.order_date).desc(), SalesOrder.invoice_number)
            .limit(MAX_INVOICE_OPTIONS)
        )
    ).all()
    return [InvoiceOptionRead(invoice_number=number, sale_count=count) for number, count in rows]


async def list_sales_log_exceptions(
    db: AsyncSession,
    pagination: PaginationParams,
    *,
    search: str | None = None,
    kind: str | None = None,
    party_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> SalesLogExceptionListRead:
    _validate_date_range(date_from, date_to)
    offset = (pagination.page - 1) * pagination.page_size

    filters = []
    if kind is not None:
        filters.append(SalesLogException.kind == kind)
    if party_id is not None:
        filters.append(SalesLogException.party_id == party_id)
    if date_from is not None:
        filters.append(SalesLogException.entry_date >= date_from)
    if date_to is not None:
        filters.append(SalesLogException.entry_date <= date_to)
    if search is not None and search.strip():
        pattern = f"%{escape_like(search.strip())}%"
        filters.append(
            or_(
                SalesLogException.invoice_number.ilike(pattern, escape="\\"),
                SalesLogException.note.ilike(pattern, escape="\\"),
            )
        )

    total = await db.scalar(select(func.count()).select_from(SalesLogException).where(*filters))
    kind_rows = (
        await db.execute(
            select(SalesLogException.kind, func.count(), func.coalesce(func.sum(SalesLogException.amount_pkr), 0))
            .where(*filters)
            .group_by(SalesLogException.kind)
            .order_by(SalesLogException.kind)
        )
    ).all()
    totals_by_kind = [
        SalesLogExceptionKindTotalRead(kind=row_kind, count=count, total_pkr=money(amount))
        for row_kind, count, amount in kind_rows
    ]

    result = await db.execute(
        select(SalesLogException)
        .options(joinedload(SalesLogException.party))
        .where(*filters)
        .order_by(SalesLogException.entry_date.desc(), SalesLogException.id.desc())
        .offset(offset)
        .limit(pagination.page_size)
    )
    items = result.scalars().all()

    return SalesLogExceptionListRead(
        items=items,
        total=total or 0,
        page=pagination.page,
        page_size=pagination.page_size,
        total_amount_pkr=money(sum((entry.total_pkr for entry in totals_by_kind), Decimal(0))),
        totals_by_kind=totals_by_kind,
    )
