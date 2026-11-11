from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.catalog.models import Brand, Category, Item, ItemCompatibleModel, Model
from src.expenses.models import Expense, ExpenseCategory
from src.inventory.models import StockLot, StockMovement
from src.ledger.models import LedgerEntry
from src.parties.models import Party
from src.payments import service as payments_service
from src.reporting.exceptions import InvalidReportPeriod
from src.reporting.schemas import (
    BalanceStatementRead,
    ExpenseCategoryTotalRead,
    MarginReportEntryRead,
    MarginReportRead,
    PartyBalanceRead,
    ProfitLossPeriodRead,
    ProfitLossRead,
    ReorderPriorityEntryRead,
    ReorderPriorityRead,
    SellThroughEntryRead,
    SellThroughRead,
    StockListEntryRead,
    StockListRead,
    UnitemisedSalesKindRead,
)
from src.reporting.utils import money, previous_period, validate_period
from src.sales.models import SalesLogException, SalesOrder, SalesOrderLine, SalesOrderLineLot


async def get_balance_statement(db: AsyncSession) -> BalanceStatementRead:
    cash_accounts = await payments_service.get_account_balances(db)
    total_cash_pkr = money(sum((a.balance for a in cash_accounts), Decimal(0)))

    party_rows = (
        await db.execute(
            select(Party.id, Party.name, Party.roles, func.sum(LedgerEntry.debit - LedgerEntry.credit))
            .join(LedgerEntry, LedgerEntry.party_id == Party.id)
            .group_by(Party.id, Party.name, Party.roles)
            .having(func.sum(LedgerEntry.debit - LedgerEntry.credit) != 0)
        )
    ).all()
    party_balances = [
        PartyBalanceRead(party_id=pid, name=name, roles=roles, balance_pkr=money(balance))
        for pid, name, roles, balance in party_rows
    ]
    total_receivable_pkr = money(sum((p.balance_pkr for p in party_balances if p.balance_pkr > 0), Decimal(0)))
    total_payable_pkr = money(sum((-p.balance_pkr for p in party_balances if p.balance_pkr < 0), Decimal(0)))

    inventory_value_pkr = money(
        (
            await db.scalar(
                select(func.sum(StockLot.qty_remaining * StockLot.landed_cost_pkr)).where(
                    StockLot.qty_remaining > 0
                )
            )
        )
        or Decimal(0)
    )

    net_position_pkr = money(total_cash_pkr + total_receivable_pkr - total_payable_pkr + inventory_value_pkr)

    return BalanceStatementRead(
        as_of=date.today(),
        cash_accounts=cash_accounts,
        total_cash_pkr=total_cash_pkr,
        party_balances=party_balances,
        total_receivable_pkr=total_receivable_pkr,
        total_payable_pkr=total_payable_pkr,
        inventory_value_pkr=inventory_value_pkr,
        net_position_pkr=net_position_pkr,
    )


def _resolve_period(window_days: int, date_from: date | None, date_to: date | None) -> tuple[date, date, int]:
    """The report period: an explicit date_from + date_to (both required together, validated like the
    profit-loss period), otherwise the last `window_days` days up to today. Returns (start, end, days)."""
    if date_from is None and date_to is None:
        end_date = date.today()
        return end_date - timedelta(days=window_days), end_date, window_days
    if date_from is None or date_to is None:
        raise InvalidReportPeriod("Give both date_from and date_to, or neither")
    validate_period(date_from, date_to)
    return date_from, date_to, (date_to - date_from).days + 1


async def _rank_models_by_sell_through(
    db: AsyncSession, window_days: int, date_from: date | None = None, date_to: date | None = None
) -> tuple[date, date, list[tuple[Model, Decimal, int]]]:
    start_date, end_date, _days = _resolve_period(window_days, date_from, date_to)

    qty_by_item = (
        select(
            SalesOrderLine.item_id.label("item_id"),
            func.sum(SalesOrderLine.qty).label("qty_sold"),
        )
        .join(SalesOrder, SalesOrder.id == SalesOrderLine.sales_order_id)
        .where(SalesOrder.order_date >= start_date, SalesOrder.order_date <= end_date, SalesOrder.shown_only.is_(False))
        .group_by(SalesOrderLine.item_id)
        .subquery()
    )
    qty_by_model = (
        select(
            Item.model_id.label("model_id"),
            func.sum(qty_by_item.c.qty_sold).label("qty_sold"),
        )
        .select_from(Item)
        .join(qty_by_item, qty_by_item.c.item_id == Item.id)
        .group_by(Item.model_id)
        .subquery()
    )

    rows = (
        await db.execute(
            select(Model, func.coalesce(qty_by_model.c.qty_sold, Decimal(0)))
            .select_from(Model)
            .outerjoin(qty_by_model, qty_by_model.c.model_id == Model.id)
            .where(Model.is_active.is_(True))
            .order_by(func.coalesce(qty_by_model.c.qty_sold, Decimal(0)).desc(), Model.id)
        )
    ).all()
    return start_date, end_date, [(model, money(qty), rank) for rank, (model, qty) in enumerate(rows, start=1)]


async def get_sell_through(
    db: AsyncSession, window_days: int, date_from: date | None = None, date_to: date | None = None
) -> SellThroughRead:
    start_date, end_date, ranked = await _rank_models_by_sell_through(db, window_days, date_from, date_to)
    return SellThroughRead(
        window_days=(end_date - start_date).days + (1 if date_from else 0),
        start_date=start_date,
        end_date=end_date,
        entries=[
            SellThroughEntryRead(model_id=m.id, model_name=m.name, qty_sold=qty, rank=rank)
            for m, qty, rank in ranked
        ],
    )


async def recalculate_reorder_priority(db: AsyncSession, window_days: int) -> ReorderPriorityRead:
    start_date, end_date, ranked = await _rank_models_by_sell_through(db, window_days)
    for model, _qty, rank in ranked:
        model.priority = rank
    await db.commit()
    return ReorderPriorityRead(
        window_days=window_days,
        start_date=start_date,
        end_date=end_date,
        entries=[
            ReorderPriorityEntryRead(model_id=m.id, model_name=m.name, qty_sold=qty, priority=rank)
            for m, qty, rank in ranked
        ],
    )


def _revenue_by_item_subquery(start_date: date, end_date: date):
    """Per-item units and revenue for sales dated in [start_date, end_date]. Shared by the margin report and
    the profit-loss report so their revenue can never drift apart."""
    return (
        select(
            SalesOrderLine.item_id.label("item_id"),
            func.sum(SalesOrderLine.qty).label("qty_sold"),
            # Per-line rounding, like the stored line amounts and the ledger debit (see sales.service list totals).
            func.sum(func.round(SalesOrderLine.qty * SalesOrderLine.rate_pkr, 2)).label("revenue_pkr"),
        )
        .join(SalesOrder, SalesOrder.id == SalesOrderLine.sales_order_id)
        .where(SalesOrder.order_date >= start_date, SalesOrder.order_date <= end_date, SalesOrder.shown_only.is_(False))
        .group_by(SalesOrderLine.item_id)
        .subquery()
    )


def _cost_by_item_subquery(start_date: date, end_date: date):
    """Per-item FIFO cost of goods for sales dated in [start_date, end_date], from the unit cost snapshotted
    on each SalesOrderLineLot at sale time. Kept a separate aggregate from revenue on purpose: joining the lot
    rows into the revenue query would multiply qty * rate_pkr by the number of lots a line drew from."""
    # A line's cost is rounded once per LINE (SalesOrderLineRead.cost_pkr), so aggregate per line first,
    # then sum those rounded line costs per item.
    per_line = (
        select(
            SalesOrderLine.id.label("line_id"),
            SalesOrderLine.item_id.label("item_id"),
            func.round(func.sum(SalesOrderLineLot.qty_consumed * SalesOrderLineLot.unit_cost_pkr), 2).label("cost"),
        )
        .select_from(SalesOrderLineLot)
        .join(SalesOrderLine, SalesOrderLine.id == SalesOrderLineLot.sales_order_line_id)
        .join(SalesOrder, SalesOrder.id == SalesOrderLine.sales_order_id)
        .where(SalesOrder.order_date >= start_date, SalesOrder.order_date <= end_date, SalesOrder.shown_only.is_(False))
        .group_by(SalesOrderLine.id, SalesOrderLine.item_id)
        .subquery()
    )
    return (
        select(per_line.c.item_id.label("item_id"), func.sum(per_line.c.cost).label("cost_pkr"))
        .group_by(per_line.c.item_id)
        .subquery()
    )


async def get_margin_report(
    db: AsyncSession, window_days: int, date_from: date | None = None, date_to: date | None = None
) -> MarginReportRead:
    start_date, end_date, window_days = _resolve_period(window_days, date_from, date_to)

    revenue_by_item = _revenue_by_item_subquery(start_date, end_date)
    cost_by_item = _cost_by_item_subquery(start_date, end_date)

    rows = (
        await db.execute(
            select(
                Item.id,
                Item.sku,
                Model.id,
                Model.name,
                revenue_by_item.c.qty_sold,
                revenue_by_item.c.revenue_pkr,
                cost_by_item.c.cost_pkr,
            )
            .select_from(revenue_by_item)
            .join(Item, Item.id == revenue_by_item.c.item_id)
            .join(Model, Model.id == Item.model_id)
            .outerjoin(cost_by_item, cost_by_item.c.item_id == revenue_by_item.c.item_id)
            .order_by(revenue_by_item.c.revenue_pkr.desc())
        )
    ).all()

    entries = []
    for item_id, sku, model_id, model_name, qty_sold, revenue_pkr, cost_pkr in rows:
        cost_pkr = cost_pkr or Decimal(0)
        margin_pkr = money(revenue_pkr - cost_pkr)
        margin_pct = float(round((margin_pkr / revenue_pkr) * 100, 2)) if revenue_pkr else 0.0
        entries.append(
            MarginReportEntryRead(
                item_id=item_id,
                sku=sku,
                model_id=model_id,
                model_name=model_name,
                qty_sold=money(qty_sold),
                revenue_pkr=money(revenue_pkr),
                cost_pkr=money(cost_pkr),
                margin_pkr=margin_pkr,
                margin_pct=margin_pct,
            )
        )

    total_revenue_pkr = money(sum((e.revenue_pkr for e in entries), Decimal(0)))
    total_cost_pkr = money(sum((e.cost_pkr for e in entries), Decimal(0)))
    total_margin_pkr = money(total_revenue_pkr - total_cost_pkr)

    return MarginReportRead(
        window_days=window_days,
        start_date=start_date,
        end_date=end_date,
        entries=entries,
        total_revenue_pkr=total_revenue_pkr,
        total_cost_pkr=total_cost_pkr,
        total_margin_pkr=total_margin_pkr,
    )


def _pct(numerator: Decimal, denominator: Decimal) -> float:
    return float(round((numerator / denominator) * 100, 2)) if denominator else 0.0


async def _compute_period(
    db: AsyncSession, date_from: date, date_to: date, include_unitemised: bool
) -> ProfitLossPeriodRead:
    """One period of the profit & loss statement, read straight from the domain tables (not the ledger — it
    carries no revenue/COGS/expense accounts). Money in and out of cash (customer payments, vendor payments)
    and stock purchases are deliberately absent: they are cash/assets, not profit."""
    revenue_by_item = _revenue_by_item_subquery(date_from, date_to)
    cost_by_item = _cost_by_item_subquery(date_from, date_to)

    items_revenue, units_sold = (
        await db.execute(
            select(
                func.coalesce(func.sum(revenue_by_item.c.revenue_pkr), 0),
                func.coalesce(func.sum(revenue_by_item.c.qty_sold), 0),
            )
        )
    ).one()
    cogs = await db.scalar(select(func.coalesce(func.sum(cost_by_item.c.cost_pkr), 0)))

    order_count = await db.scalar(
        select(func.count(SalesOrder.id)).where(
            SalesOrder.order_date >= date_from, SalesOrder.order_date <= date_to, SalesOrder.shown_only.is_(False)
        )
    )
    lines_without_cost = await db.scalar(
        select(func.count(SalesOrderLine.id))
        .join(SalesOrder, SalesOrder.id == SalesOrderLine.sales_order_id)
        .where(
            SalesOrder.order_date >= date_from,
            SalesOrder.order_date <= date_to,
            SalesOrder.shown_only.is_(False),
            ~select(SalesOrderLineLot.id).where(SalesOrderLineLot.sales_order_line_id == SalesOrderLine.id).exists(),
        )
    )

    # Value of stock that left the shelf without a sale: a damaged write-off is a loss, a negative adjustment is
    # a loss, a positive adjustment (recount found more) reduces it. "receipt" and "sale" movements are not
    # losses — receipts add stock, sales are already in COGS.
    stock_loss = await db.scalar(
        select(func.coalesce(func.sum(-StockMovement.qty_delta * StockLot.landed_cost_pkr), 0))
        .select_from(StockMovement)
        .join(StockLot, StockLot.id == StockMovement.stock_lot_id)
        .where(
            StockMovement.movement_type.in_(("damaged", "adjustment")),
            StockMovement.movement_date >= date_from,
            StockMovement.movement_date <= date_to,
        )
    )

    expense_rows = (
        await db.execute(
            select(ExpenseCategory.id, ExpenseCategory.name, ExpenseCategory.frequency, func.sum(Expense.amount))
            .join(ExpenseCategory, ExpenseCategory.id == Expense.category_id)
            .where(
                Expense.status == "confirmed",
                ExpenseCategory.counts_toward_profit.is_(True),
                Expense.shown_only.is_(False),
                Expense.expense_date >= date_from,
                Expense.expense_date <= date_to,
            )
            .group_by(ExpenseCategory.id, ExpenseCategory.name, ExpenseCategory.frequency)
            .order_by(func.sum(Expense.amount).desc(), ExpenseCategory.name)
        )
    ).all()
    expenses_by_category = [
        ExpenseCategoryTotalRead(category_id=cid, category_name=name, frequency=frequency, total_pkr=money(total))
        for cid, name, frequency, total in expense_rows
    ]
    expenses_total = sum((e.total_pkr for e in expenses_by_category), Decimal(0))
    excluded_expenses = await db.scalar(
        select(func.coalesce(func.sum(Expense.amount), 0))
        .join(ExpenseCategory, ExpenseCategory.id == Expense.category_id)
        .where(
            Expense.status == "confirmed",
            ExpenseCategory.counts_toward_profit.is_(False),
            Expense.shown_only.is_(False),
            Expense.expense_date >= date_from,
            Expense.expense_date <= date_to,
        )
    )
    draft_expenses = await db.scalar(
        select(func.coalesce(func.sum(Expense.amount), 0)).where(
            Expense.status == "draft",
            Expense.shown_only.is_(False),
            Expense.expense_date >= date_from,
            Expense.expense_date <= date_to,
        )
    )

    unitemised_rows = (
        await db.execute(
            select(SalesLogException.kind, func.count(SalesLogException.id), func.sum(SalesLogException.amount_pkr))
            .where(SalesLogException.entry_date >= date_from, SalesLogException.entry_date <= date_to)
            .group_by(SalesLogException.kind)
            .order_by(SalesLogException.kind)
        )
    ).all()
    unitemised_by_kind = [
        UnitemisedSalesKindRead(kind=kind, count=count, total_pkr=money(total)) for kind, count, total in unitemised_rows
    ]
    unitemised_total = sum((u.total_pkr for u in unitemised_by_kind), Decimal(0))

    # Unitemised sales carry no cost, so adding them to revenue overstates gross profit — opt-in only.
    revenue = money(items_revenue) + (unitemised_total if include_unitemised else Decimal(0))
    cogs = money(cogs)
    gross_profit = money(revenue - cogs)
    stock_loss = money(stock_loss)
    expenses_total = money(expenses_total)
    net_profit = money(gross_profit - stock_loss - expenses_total)

    return ProfitLossPeriodRead(
        date_from=date_from,
        date_to=date_to,
        revenue_pkr=revenue,
        cogs_pkr=cogs,
        gross_profit_pkr=gross_profit,
        gross_margin_pct=_pct(gross_profit, revenue),
        stock_loss_pkr=stock_loss,
        expenses_total_pkr=expenses_total,
        expenses_by_category=expenses_by_category,
        net_profit_pkr=net_profit,
        net_margin_pct=_pct(net_profit, revenue),
        units_sold=money(units_sold),
        order_count=order_count or 0,
        unitemised_sales_pkr=money(unitemised_total),
        unitemised_sales_by_kind=unitemised_by_kind,
        draft_expenses_pkr=money(draft_expenses or Decimal(0)),
        excluded_expenses_pkr=money(excluded_expenses or Decimal(0)),
        lines_without_cost=lines_without_cost or 0,
    )


async def get_profit_loss(
    db: AsyncSession,
    date_from: date,
    date_to: date,
    compare_previous: bool = False,
    include_unitemised: bool = False,
) -> ProfitLossRead:
    validate_period(date_from, date_to)

    current = await _compute_period(db, date_from, date_to, include_unitemised)
    previous = None
    if compare_previous:
        prev_from, prev_to = previous_period(date_from, date_to)
        previous = await _compute_period(db, prev_from, prev_to, include_unitemised)

    warnings = []
    if current.draft_expenses_pkr > 0:
        warnings.append(f"Draft expenses of {current.draft_expenses_pkr} are not included — confirm them to count.")
    if current.unitemised_sales_pkr != 0:
        if include_unitemised:
            warnings.append(
                f"Sales without item data ({current.unitemised_sales_pkr}) are included in revenue with no cost, "
                "so gross profit is overstated by their unknown cost."
            )
        else:
            warnings.append(
                f"Sales without item data ({current.unitemised_sales_pkr}) are not included in profit."
            )
    if current.lines_without_cost > 0:
        warnings.append(
            f"{current.lines_without_cost} sale line(s) have no recorded cost, so their cost is counted as 0."
        )

    return ProfitLossRead(current=current, previous=previous, warnings=warnings)


async def get_stock_list(db: AsyncSession, in_stock_only: bool = True) -> StockListRead:
    # Before real stock is being tracked (freshly seeded catalog, no PurchaseOrders/
    # StockLots yet), in_stock_only=False lets the whole active catalog be
    # downloaded anyway — deliberately NOT solved by faking StockLot rows, which
    # would need real PurchaseOrderLine/vendor/ledger records behind them per this
    # app's accounting model and would corrupt real inventory valuation later.
    extra_conditions = []
    if in_stock_only:
        in_stock_item_ids = select(StockLot.item_id).where(StockLot.qty_remaining > 0).distinct()
        extra_conditions.append(Item.id.in_(in_stock_item_ids))

    # Per-item stock on hand, reused by both queries below so a compatible
    # row can report the same "how much do I actually have" figure as the
    # item(s) it shares physical stock with.
    stock_by_item = (
        select(StockLot.item_id.label("item_id"), func.sum(StockLot.qty_remaining).label("qty_remaining"))
        .group_by(StockLot.item_id)
        .subquery()
    )

    # Primary rows: one row PER ITEM, not deduplicated by model -- two
    # differently-colored items of the same phone model (e.g. a Bolt Lens
    # Protector in Silver vs. Golden) are two distinct physical products and
    # must both show up, each with its own full "model + variant" name. Keyed
    # by the item's own id, which is naturally unique.
    primary_rows = (
        await db.execute(
            select(
                Category.name.label("category"),
                Brand.name.label("brand"),
                Model.name.label("model"),
                Item.variant.label("variant"),
                Item.id.label("entry_key"),
                func.coalesce(stock_by_item.c.qty_remaining, 0).label("qty_remaining"),
            )
            .select_from(Item)
            .join(Category, Category.id == Item.category_id)
            .join(Model, Model.id == Item.model_id)
            .join(Brand, Brand.id == Model.brand_id)
            .outerjoin(stock_by_item, stock_by_item.c.item_id == Item.id)
            .where(Item.is_active.is_(True), *extra_conditions)
            .order_by(Category.name, Brand.name, Model.name)
        )
    ).all()

    # Compatible rows: "this model also fits one of this category's items" --
    # it carries no StockLot of its own, so its qty_remaining is the sum of
    # every item it's compatible with (grouping replaces the old .distinct(),
    # since a model compatible with several items now aggregates their stock
    # into one row instead of one row per item).
    compatible_rows = (
        await db.execute(
            select(
                Category.name.label("category"),
                Brand.name.label("brand"),
                Model.name.label("model"),
                Model.id.label("model_id"),
                func.coalesce(func.sum(func.coalesce(stock_by_item.c.qty_remaining, 0)), 0).label("qty_remaining"),
            )
            .select_from(Item)
            .join(Category, Category.id == Item.category_id)
            .join(ItemCompatibleModel, ItemCompatibleModel.item_id == Item.id)
            .join(Model, Model.id == ItemCompatibleModel.model_id)
            .join(Brand, Brand.id == Model.brand_id)
            .outerjoin(stock_by_item, stock_by_item.c.item_id == Item.id)
            .where(Item.is_active.is_(True), *extra_conditions)
            .group_by(Category.name, Brand.name, Model.name, Model.id)
            .order_by(Category.name, Brand.name, Model.name)
        )
    ).all()

    entries = [
        StockListEntryRead(
            category=r.category,
            brand=r.brand,
            model=f"{r.model} {r.variant}" if r.variant else r.model,
            model_id=r.entry_key,
            qty_remaining=r.qty_remaining,
        )
        for r in primary_rows
    ] + [
        StockListEntryRead(
            category=r.category, brand=r.brand, model=r.model, model_id=-r.model_id, qty_remaining=r.qty_remaining
        )
        for r in compatible_rows
    ]
    entries.sort(key=lambda e: (e.category, e.brand, e.model))

    return StockListRead(entries=entries)
