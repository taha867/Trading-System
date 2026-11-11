"""The Purchases list: every supplier invoice once, with its payable-only entries under it.

A row is a supplier invoice: the purchase order(s) with that invoice number and vendor, plus every payable-only entry
(purchase_log_exception: money owed to the supplier, no phone model, so no stock) with the same number and vendor. An
order or entry without an invoice number is its own row. Rows, page and summary totals come from ONE grouped query,
so the summary can never disagree with the rows. Amounts are the ledger's (per-line rounded), so a row total is what
is payable for it. Read-only. Mirrors sales/invoice_service.py.
"""
from datetime import date

from sqlalchemy import Numeric, String, cast, func, literal, not_, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from src.catalog.models import Category, Item
from src.pagination import PaginationParams
from src.parties.models import Party
from src.purchasing.constants import PurchaseShow
from src.purchasing.models import PurchaseLogException, PurchaseOrder, PurchaseOrderLine
from src.purchasing.schemas import PurchaseGroupListRead, PurchaseGroupOrderRead, PurchaseGroupRead, PurchaseLogExceptionRead
from src.purchasing.service import _order_filter_clauses, _validate_date_range
from src.purchasing.utils import escape_like, money
from src.sorting import SortDirection, date_ordering


def _entry_filter_clauses(
    *, search: str | None, invoice_number: str | None, party_id: int | None, date_from: date | None, date_to: date | None
) -> list:
    """The order filters, mapped onto the payable-only entry columns (same meaning)."""
    _validate_date_range(date_from, date_to)
    clauses = []
    if invoice_number is not None and invoice_number.strip():
        clauses.append(PurchaseLogException.invoice_number == invoice_number.strip())
    if party_id is not None:
        clauses.append(PurchaseLogException.party_id == party_id)
    if date_from is not None:
        clauses.append(PurchaseLogException.entry_date >= date_from)
    if date_to is not None:
        clauses.append(PurchaseLogException.entry_date <= date_to)
    if search is not None and search.strip():
        pattern = f"%{escape_like(search.strip())}%"
        clauses.append(
            or_(
                PurchaseLogException.invoice_number.ilike(pattern, escape="\\"),
                PurchaseLogException.note.ilike(pattern, escape="\\"),
            )
        )
    return clauses


def _parts_query(order_clauses: list, entry_clauses: list | None):
    """One row per purchase order and one per entry: (source, ref id, group key, invoice number, vendor, date, amount, rmb).
    `entry_clauses` None means "leave the entries out" (a source, status or item filter only means something for orders)."""
    line_totals = (
        select(
            PurchaseOrderLine.purchase_order_id.label("order_id"),
            func.sum(func.round(PurchaseOrderLine.qty * PurchaseOrderLine.rate_pkr, 2)).label("amount"),
            func.sum(func.round(PurchaseOrderLine.qty * PurchaseOrderLine.rate_rmb, 2)).label("rmb"),
        )
        .group_by(PurchaseOrderLine.purchase_order_id)
        .subquery()
    )
    order_key = func.coalesce(func.nullif(PurchaseOrder.invoice_number, ""), func.concat("order-", cast(PurchaseOrder.id, String)))
    orders = (
        select(
            literal("P").label("src"),
            PurchaseOrder.id.label("ref_id"),
            order_key.label("gkey"),
            PurchaseOrder.invoice_number.label("invoice_number"),
            PurchaseOrder.party_id.label("party_id"),
            PurchaseOrder.order_date.label("d"),
            cast(func.coalesce(line_totals.c.amount, 0), Numeric(14, 2)).label("amount"),
            cast(func.coalesce(line_totals.c.rmb, 0), Numeric(14, 2)).label("rmb"),
        )
        .select_from(PurchaseOrder)
        .outerjoin(line_totals, line_totals.c.order_id == PurchaseOrder.id)
        .where(*order_clauses)
    )
    if entry_clauses is None:
        return orders.subquery("parts")
    entry_key = func.coalesce(func.nullif(PurchaseLogException.invoice_number, ""), func.concat("entry-", cast(PurchaseLogException.id, String)))
    entries = select(
        literal("E").label("src"),
        PurchaseLogException.id.label("ref_id"),
        entry_key.label("gkey"),
        PurchaseLogException.invoice_number.label("invoice_number"),
        PurchaseLogException.party_id.label("party_id"),
        PurchaseLogException.entry_date.label("d"),
        cast(PurchaseLogException.amount_pkr, Numeric(14, 2)).label("amount"),
        cast(literal(0), Numeric(14, 2)).label("rmb"),
    ).where(*entry_clauses)
    return union_all(orders, entries).subquery("parts")


async def list_purchase_groups(
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
    show: PurchaseShow = "all",
    sort: SortDirection = "newest",
) -> PurchaseGroupListRead:
    order_clauses = _order_filter_clauses(
        search=search, invoice_number=invoice_number, party_id=party_id, source=source, status=status,
        date_from=date_from, date_to=date_to, item_id=item_id,
    )
    # Payable-only entries come from local purchases: a Mohsin / China source, a status or an item filter leaves them out.
    entries_apply = (source in (None, "local")) and status is None and item_id is None
    entry_clauses = (
        _entry_filter_clauses(search=search, invoice_number=invoice_number, party_id=party_id, date_from=date_from, date_to=date_to)
        if entries_apply
        else None
    )
    parts = _parts_query(order_clauses, entry_clauses)

    is_entry = parts.c.src == "E"
    grouped = select(
        parts.c.gkey,
        func.max(parts.c.invoice_number).label("invoice_number"),
        parts.c.party_id,
        func.max(parts.c.d).label("d"),
        func.max(parts.c.ref_id).label("sort_id"),
        func.sum(parts.c.amount).label("total"),
        func.coalesce(func.sum(parts.c.amount).filter(parts.c.src == "P"), 0).label("orders"),
        func.coalesce(func.sum(parts.c.amount).filter(is_entry), 0).label("entries"),
        func.sum(parts.c.rmb).label("rmb"),
        func.array_agg(parts.c.ref_id).filter(parts.c.src == "P").label("order_ids"),
        func.array_agg(parts.c.ref_id).filter(is_entry).label("entry_ids"),
    ).group_by(parts.c.gkey, parts.c.party_id)
    if show == "orders_only":
        grouped = grouped.having(not_(func.bool_or(is_entry)))
    elif show == "payable_only":
        grouped = grouped.having(func.bool_or(is_entry))
    g = grouped.subquery("g")

    total_count, total_pkr, orders_pkr, entries_pkr, total_rmb = (
        await db.execute(
            select(
                func.count(),
                func.coalesce(func.sum(g.c.total), 0),
                func.coalesce(func.sum(g.c.orders), 0),
                func.coalesce(func.sum(g.c.entries), 0),
                func.coalesce(func.sum(g.c.rmb), 0),
            ).select_from(g)
        )
    ).one()

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

    order_ids = sorted({i for row in page_rows for i in (row.order_ids or [])})
    entry_ids = sorted({i for row in page_rows for i in (row.entry_ids or [])})
    order_rows: dict[int, PurchaseGroupOrderRead] = {}
    if order_ids:
        summary = (
            await db.execute(
                select(parts.c.ref_id, parts.c.d, parts.c.amount, parts.c.rmb, PurchaseOrder.source, PurchaseOrder.status)
                .select_from(parts)
                .join(PurchaseOrder, PurchaseOrder.id == parts.c.ref_id)
                .where(parts.c.src == "P", parts.c.ref_id.in_(order_ids))
            )
        ).all()
        categories: dict[int, set[str]] = {}
        for order_id, name in (
            await db.execute(
                select(PurchaseOrderLine.purchase_order_id, Category.name)
                .join(Item, Item.id == PurchaseOrderLine.item_id)
                .join(Category, Category.id == Item.category_id)
                .where(PurchaseOrderLine.purchase_order_id.in_(order_ids))
            )
        ).all():
            categories.setdefault(order_id, set()).add(name)
        for row in summary:
            order_rows[row.ref_id] = PurchaseGroupOrderRead(
                id=row.ref_id, order_date=row.d, source=row.source, status=row.status,
                total_pkr=money(row.amount), total_rmb=money(row.rmb), categories=sorted(categories.get(row.ref_id, set())),
            )
    entries_by_id: dict[int, PurchaseLogExceptionRead] = {}
    if entry_ids:
        found = await db.execute(
            select(PurchaseLogException).options(joinedload(PurchaseLogException.party)).where(PurchaseLogException.id.in_(entry_ids))
        )
        entries_by_id = {e.id: PurchaseLogExceptionRead.model_validate(e) for e in found.scalars().all()}

    items = []
    for row in page_rows:
        row_orders = [order_rows[i] for i in sorted(row.order_ids or []) if i in order_rows]
        row_entries = [entries_by_id[i] for i in sorted(row.entry_ids or []) if i in entries_by_id]
        cats = sorted({c for o in row_orders for c in o.categories} | {e.category_name for e in row_entries if e.category_name})
        items.append(
            PurchaseGroupRead(
                group_key=row.gkey, invoice_number=row.invoice_number or None, party_id=row.party_id, party_name=row.party_name or "",
                invoice_date=row.d, total_pkr=money(row.total), orders_pkr=money(row.orders), entries_pkr=money(row.entries),
                total_rmb=money(row.rmb), categories=cats, orders=row_orders, entries=row_entries,
            )
        )
    return PurchaseGroupListRead(
        items=items, total=total_count or 0, page=pagination.page, page_size=pagination.page_size,
        total_pkr=money(total_pkr), orders_pkr=money(orders_pkr), entries_pkr=money(entries_pkr), total_rmb=money(total_rmb),
    )
