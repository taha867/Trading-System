from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import func, select, union
from sqlalchemy.ext.asyncio import AsyncSession

from src.catalog.models import Brand, Category, Item, ItemCompatibleModel, Model
from src.inventory.models import StockLot
from src.ledger.models import LedgerEntry
from src.parties.models import Party
from src.payments import service as payments_service
from src.reporting.schemas import (
    BalanceStatementRead,
    MarginReportEntryRead,
    MarginReportRead,
    PartyBalanceRead,
    ReorderPriorityEntryRead,
    ReorderPriorityRead,
    SellThroughEntryRead,
    SellThroughRead,
    StockListEntryRead,
    StockListRead,
)
from src.reporting.utils import money
from src.sales.models import SalesOrder, SalesOrderLine, SalesOrderLineLot


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


async def _rank_models_by_sell_through(
    db: AsyncSession, window_days: int
) -> tuple[date, date, list[tuple[Model, Decimal, int]]]:
    end_date = date.today()
    start_date = end_date - timedelta(days=window_days)

    qty_by_item = (
        select(
            SalesOrderLine.item_id.label("item_id"),
            func.sum(SalesOrderLine.qty).label("qty_sold"),
        )
        .join(SalesOrder, SalesOrder.id == SalesOrderLine.sales_order_id)
        .where(SalesOrder.order_date >= start_date, SalesOrder.order_date <= end_date)
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


async def get_sell_through(db: AsyncSession, window_days: int) -> SellThroughRead:
    start_date, end_date, ranked = await _rank_models_by_sell_through(db, window_days)
    return SellThroughRead(
        window_days=window_days,
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


async def get_margin_report(db: AsyncSession, window_days: int) -> MarginReportRead:
    end_date = date.today()
    start_date = end_date - timedelta(days=window_days)

    revenue_by_item = (
        select(
            SalesOrderLine.item_id.label("item_id"),
            func.sum(SalesOrderLine.qty).label("qty_sold"),
            func.sum(SalesOrderLine.qty * SalesOrderLine.rate_pkr).label("revenue_pkr"),
        )
        .join(SalesOrder, SalesOrder.id == SalesOrderLine.sales_order_id)
        .where(SalesOrder.order_date >= start_date, SalesOrder.order_date <= end_date)
        .group_by(SalesOrderLine.item_id)
        .subquery()
    )
    cost_by_item = (
        select(
            SalesOrderLine.item_id.label("item_id"),
            func.sum(SalesOrderLineLot.qty_consumed * SalesOrderLineLot.unit_cost_pkr).label("cost_pkr"),
        )
        .select_from(SalesOrderLineLot)
        .join(SalesOrderLine, SalesOrderLine.id == SalesOrderLineLot.sales_order_line_id)
        .join(SalesOrder, SalesOrder.id == SalesOrderLine.sales_order_id)
        .where(SalesOrder.order_date >= start_date, SalesOrder.order_date <= end_date)
        .group_by(SalesOrderLine.item_id)
        .subquery()
    )

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

    primary = (
        select(
            Category.name.label("category"),
            Brand.name.label("brand"),
            Model.name.label("model"),
            Model.id.label("model_id"),
        )
        .select_from(Item)
        .join(Category, Category.id == Item.category_id)
        .join(Model, Model.id == Item.model_id)
        .join(Brand, Brand.id == Model.brand_id)
        .where(Item.is_active.is_(True), *extra_conditions)
    )

    compatible = (
        select(
            Category.name.label("category"),
            Brand.name.label("brand"),
            Model.name.label("model"),
            Model.id.label("model_id"),
        )
        .select_from(Item)
        .join(Category, Category.id == Item.category_id)
        .join(ItemCompatibleModel, ItemCompatibleModel.item_id == Item.id)
        .join(Model, Model.id == ItemCompatibleModel.model_id)
        .join(Brand, Brand.id == Model.brand_id)
        .where(Item.is_active.is_(True), *extra_conditions)
    )

    combined = union(primary, compatible).subquery()
    rows = (
        await db.execute(
            select(combined.c.category, combined.c.brand, combined.c.model, combined.c.model_id).order_by(
                combined.c.category, combined.c.brand, combined.c.model
            )
        )
    ).all()

    return StockListRead(
        entries=[
            StockListEntryRead(category=r.category, brand=r.brand, model=r.model, model_id=r.model_id)
            for r in rows
        ]
    )
