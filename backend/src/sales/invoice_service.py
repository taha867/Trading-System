"""The Invoices list: every invoice once, with its day-book entries ("No stock found", bulk, correction, ...) under it.

An invoice is a sale plus every sales_log_exception row that has the same invoice number and customer. Both come from
tables the Sales screens already use; nothing here writes. The rows, the page and the summary totals are all computed
from ONE grouped query, so the summary bar can never disagree with the rows (same idea as service.list_sales_orders).
The amounts are the ledger's: a sale counts its per-line rounded total, an entry its own amount, so an invoice total is
exactly what the customer's balance holds for it.
"""
from datetime import date
from decimal import Decimal

from sqlalchemy import Numeric, String, and_, case, cast, func, literal, not_, null, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, joinedload

from src.pagination import PaginationParams
from src.parties.models import Party
from src.sales.constants import InvoiceShow
from src.sales.models import SalesLogException, SalesOrder, SalesOrderLine, SalesOrderLineLot
from src.sales.schemas import InvoiceGroupRead, InvoiceListRead, InvoiceOrderRead, SalesLogExceptionRead
from src.sales.service import _order_filter_clauses, _validate_date_range
from src.sales.utils import escape_like, money
from src.sorting import SortDirection, date_ordering

NOT_A_SALE_LINE = ("insufficient_stock", "cancelled_invoice")  # every other entry kind is "other entries"


def _entry_filter_clauses(
    *, search: str | None, invoice_number: str | None, party_id: int | None, date_from: date | None, date_to: date | None
) -> list:
    """The sales filters, mapped onto the day-book columns (same meaning as the sales side)."""
    _validate_date_range(date_from, date_to)
    clauses = []
    if invoice_number is not None and invoice_number.strip():
        clauses.append(SalesLogException.invoice_number == invoice_number.strip())
    if party_id is not None:
        clauses.append(SalesLogException.party_id == party_id)
    if date_from is not None:
        clauses.append(SalesLogException.entry_date >= date_from)
    if date_to is not None:
        clauses.append(SalesLogException.entry_date <= date_to)
    if search is not None and search.strip():
        clauses.append(SalesLogException.invoice_number.ilike(f"%{escape_like(search.strip())}%", escape="\\"))
    return clauses


def _parts_query(sale_clauses: list, entry_clauses: list | None):
    """One row per sale and one per entry: (source, ref id, invoice number, customer, date, kind, amount, cost).
    `entry_clauses` None means "leave the entries out" (an item filter only means something for sales)."""
    line_amount = (
        select(
            SalesOrderLine.sales_order_id.label("order_id"),
            func.sum(func.round(SalesOrderLine.qty * SalesOrderLine.rate_pkr, 2)).label("amount"),
        )
        .group_by(SalesOrderLine.sales_order_id)
        .subquery()
    )
    # cost is rounded PER LINE then summed, exactly like the sale's own margin and the ledger
    per_line_cost = (
        select(
            SalesOrderLine.sales_order_id.label("order_id"),
            func.round(func.sum(SalesOrderLineLot.qty_consumed * SalesOrderLineLot.unit_cost_pkr), 2).label("cost"),
        )
        .select_from(SalesOrderLineLot)
        .join(SalesOrderLine, SalesOrderLine.id == SalesOrderLineLot.sales_order_line_id)
        .group_by(SalesOrderLine.id, SalesOrderLine.sales_order_id)
        .subquery()
    )
    order_cost = select(per_line_cost.c.order_id, func.sum(per_line_cost.c.cost).label("cost")).group_by(per_line_cost.c.order_id).subquery()

    # an invoice with no number is its own group (never merged with another blank one)
    sale_key = func.coalesce(func.nullif(SalesOrder.invoice_number, ""), func.concat("sale-", cast(SalesOrder.id, String)))
    sales = (
        select(
            literal("S").label("src"),
            SalesOrder.id.label("ref_id"),
            sale_key.label("gkey"),
            SalesOrder.invoice_number.label("invoice_number"),
            SalesOrder.party_id.label("party_id"),
            SalesOrder.order_date.label("d"),
            cast(null(), String).label("kind"),
            cast(func.coalesce(line_amount.c.amount, 0), Numeric(14, 2)).label("amount"),
            cast(func.coalesce(order_cost.c.cost, 0), Numeric(14, 2)).label("cost"),
        )
        .select_from(SalesOrder)
        .outerjoin(line_amount, line_amount.c.order_id == SalesOrder.id)
        .outerjoin(order_cost, order_cost.c.order_id == SalesOrder.id)
        .where(*sale_clauses)
    )
    if entry_clauses is None:
        return sales.subquery("parts")
    entry_key = func.coalesce(func.nullif(SalesLogException.invoice_number, ""), func.concat("entry-", cast(SalesLogException.id, String)))
    entries = select(
        literal("E").label("src"),
        SalesLogException.id.label("ref_id"),
        entry_key.label("gkey"),
        SalesLogException.invoice_number.label("invoice_number"),
        SalesLogException.party_id.label("party_id"),
        SalesLogException.entry_date.label("d"),
        SalesLogException.kind.label("kind"),
        cast(SalesLogException.amount_pkr, Numeric(14, 2)).label("amount"),
        cast(literal(0), Numeric(14, 2)).label("cost"),
    ).where(*entry_clauses)
    return union_all(sales, entries).subquery("parts")


async def list_invoices(
    db: AsyncSession,
    pagination: PaginationParams,
    *,
    search: str | None = None,
    invoice_number: str | None = None,
    party_id: int | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    item_id: int | None = None,
    show: InvoiceShow = "all",
    sort: SortDirection = "newest",
) -> InvoiceListRead:
    sale_clauses = _order_filter_clauses(
        search=search, invoice_number=invoice_number, party_id=party_id, date_from=date_from, date_to=date_to, item_id=item_id
    )
    entry_clauses = (
        None
        if item_id is not None
        else _entry_filter_clauses(search=search, invoice_number=invoice_number, party_id=party_id, date_from=date_from, date_to=date_to)
    )
    parts = _parts_query(sale_clauses, entry_clauses)

    is_entry = parts.c.src == "E"
    is_other_entry = and_(is_entry, not_(parts.c.kind.in_(NOT_A_SALE_LINE)))
    no_stock = parts.c.kind == "insufficient_stock"
    cancelled = parts.c.kind == "cancelled_invoice"

    def sum_where(condition, column=parts.c.amount):
        return func.coalesce(func.sum(case((condition, column), else_=0)), 0)

    grouped = select(
        parts.c.gkey,
        func.max(parts.c.invoice_number).label("invoice_number"),
        parts.c.party_id,
        func.max(parts.c.d).label("d"),
        func.max(parts.c.ref_id).label("sort_id"),
        func.sum(parts.c.amount).label("total"),
        sum_where(parts.c.src == "S").label("booked"),
        func.sum(parts.c.cost).label("cost"),
        sum_where(no_stock).label("no_stock"),
        sum_where(is_other_entry).label("other"),
        func.bool_or(cancelled).label("is_cancelled"),
        func.array_agg(parts.c.ref_id).filter(parts.c.src == "S").label("order_ids"),
        func.array_agg(parts.c.ref_id).filter(is_entry).label("entry_ids"),
    ).group_by(parts.c.gkey, parts.c.party_id)
    if show == "has_no_stock":
        grouped = grouped.having(func.bool_or(no_stock))
    elif show == "has_other_entries":
        grouped = grouped.having(func.bool_or(is_other_entry))
    elif show == "cancelled":
        grouped = grouped.having(func.bool_or(cancelled))
    elif show == "fully_booked":
        grouped = grouped.having(not_(func.bool_or(is_entry)))
    g = grouped.subquery("g")

    totals = (
        await db.execute(
            select(
                func.count(),
                func.coalesce(func.sum(g.c.total), 0),
                func.coalesce(func.sum(g.c.booked), 0),
                func.coalesce(func.sum(g.c.cost), 0),
                func.coalesce(func.sum(g.c.no_stock), 0),
                func.coalesce(func.sum(g.c.other), 0),
                func.count().filter(g.c.is_cancelled),
            ).select_from(g)
        )
    ).one()
    total_count, total_pkr, booked_pkr, cost_pkr, no_stock_pkr, other_pkr, cancelled_count = totals

    offset = (pagination.page - 1) * pagination.page_size
    page_rows = (
        await db.execute(
            select(g, Party.name.label("party_name"))
            .select_from(g)
            .outerjoin(Party, Party.id == g.c.party_id)
            .order_by(*date_ordering(g.c.d, g.c.sort_id, sort), g.c.gkey)
            .offset(offset)
            .limit(pagination.page_size)
        )
    ).all()

    # The page's sales (summary numbers come from the same parts rows) and entries (full rows), in two batched queries.
    order_ids = sorted({i for row in page_rows for i in (row.order_ids or [])})
    entry_ids = sorted({i for row in page_rows for i in (row.entry_ids or [])})
    order_rows = {}
    if order_ids:
        for row in (await db.execute(select(parts.c.ref_id, parts.c.d, parts.c.amount, parts.c.cost).where(parts.c.src == "S", parts.c.ref_id.in_(order_ids)))).all():
            order_rows[row.ref_id] = InvoiceOrderRead(id=row.ref_id, order_date=row.d, total_pkr=money(row.amount), margin_pkr=money(row.amount - row.cost))
    entries_by_id = {}
    if entry_ids:
        found = await db.execute(
            select(SalesLogException).options(joinedload(SalesLogException.party)).where(SalesLogException.id.in_(entry_ids))
        )
        entries_by_id = {e.id: SalesLogExceptionRead.model_validate(e) for e in found.scalars().all()}

    items = []
    for row in page_rows:
        items.append(
            InvoiceGroupRead(
                group_key=row.gkey,
                invoice_number=row.invoice_number or None,
                party_id=row.party_id,
                party_name=row.party_name,
                invoice_date=row.d,
                total_pkr=money(row.total),
                booked_pkr=money(row.booked),
                margin_pkr=money(row.booked - row.cost),
                no_stock_pkr=money(row.no_stock),
                other_entries_pkr=money(row.other),
                is_cancelled=bool(row.is_cancelled),
                orders=[order_rows[i] for i in sorted(row.order_ids or []) if i in order_rows],
                entries=[entries_by_id[i] for i in sorted(row.entry_ids or []) if i in entries_by_id],
            )
        )
    return InvoiceListRead(
        items=items,
        total=total_count or 0,
        page=pagination.page,
        page_size=pagination.page_size,
        total_pkr=money(total_pkr),
        booked_pkr=money(booked_pkr),
        margin_pkr=money(booked_pkr - cost_pkr),
        no_stock_pkr=money(no_stock_pkr),
        other_entries_pkr=money(other_pkr),
        cancelled_count=cancelled_count or 0,
    )
