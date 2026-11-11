from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from src.payments.schemas import PaymentAccountBalanceRead


class PartyBalanceRead(BaseModel):
    party_id: int
    name: str
    roles: list[str]
    balance_pkr: Decimal  # positive = receivable (they owe us), negative = payable (we owe them)


class BalanceStatementRead(BaseModel):
    as_of: date
    cash_accounts: list[PaymentAccountBalanceRead]
    total_cash_pkr: Decimal
    party_balances: list[PartyBalanceRead]
    total_receivable_pkr: Decimal
    total_payable_pkr: Decimal
    inventory_value_pkr: Decimal
    net_position_pkr: Decimal


class SellThroughEntryRead(BaseModel):
    model_id: int
    model_name: str
    qty_sold: Decimal
    rank: int  # 1 = fastest mover in this window


class SellThroughRead(BaseModel):
    window_days: int
    start_date: date
    end_date: date
    entries: list[SellThroughEntryRead]


class ReorderPriorityEntryRead(BaseModel):
    model_id: int
    model_name: str
    qty_sold: Decimal
    priority: int  # the value just written to Model.priority — 1 = reorder first


class ReorderPriorityRead(BaseModel):
    window_days: int
    start_date: date
    end_date: date
    entries: list[ReorderPriorityEntryRead]


class MarginReportEntryRead(BaseModel):
    item_id: int
    sku: str
    model_id: int
    model_name: str
    qty_sold: Decimal
    revenue_pkr: Decimal
    cost_pkr: Decimal
    margin_pkr: Decimal
    margin_pct: float  # a ratio, not currency — CLAUDE.md's Decimal rule governs money fields, not this one


class MarginReportRead(BaseModel):
    window_days: int
    start_date: date
    end_date: date
    entries: list[MarginReportEntryRead]
    total_revenue_pkr: Decimal
    total_cost_pkr: Decimal
    total_margin_pkr: Decimal


class ExpenseCategoryTotalRead(BaseModel):
    category_id: int
    category_name: str
    frequency: str  # "daily" | "monthly", straight from ExpenseCategory
    total_pkr: Decimal


class UnitemisedSalesKindRead(BaseModel):
    kind: str  # SalesLogException.kind
    count: int
    total_pkr: Decimal


class ProfitLossPeriodRead(BaseModel):
    date_from: date
    date_to: date
    revenue_pkr: Decimal
    cogs_pkr: Decimal  # landed cost of the lots the sales drew from (FIFO, snapshotted at sale time)
    gross_profit_pkr: Decimal
    gross_margin_pct: float  # a ratio, not currency — same exemption as MarginReportEntryRead.margin_pct
    stock_loss_pkr: Decimal  # damaged + adjustment movements valued at lot cost; positive = net loss
    expenses_total_pkr: Decimal  # confirmed expenses only
    expenses_by_category: list[ExpenseCategoryTotalRead]
    net_profit_pkr: Decimal
    net_margin_pct: float
    units_sold: Decimal
    order_count: int
    unitemised_sales_pkr: Decimal  # SalesLogException total — in revenue_pkr only when include_unitemised=true
    unitemised_sales_by_kind: list[UnitemisedSalesKindRead]
    draft_expenses_pkr: Decimal  # excluded from profit; returned so nothing is silently hidden
    excluded_expenses_pkr: Decimal  # confirmed spending in categories that don't count toward shop profit (e.g. Personal)
    lines_without_cost: int  # sale lines in the period with no SalesOrderLineLot rows (cost counted as 0)


class ProfitLossRead(BaseModel):
    current: ProfitLossPeriodRead
    previous: ProfitLossPeriodRead | None
    warnings: list[str]


class StockListEntryRead(BaseModel):
    category: str
    brand: str
    # Full display name -- includes the item's own variant/color when it has one
    # (e.g. "iPhone 13 Pro Max Silver"), matching how the shop's own stock sheets
    # write it, so two differently-colored items of the same phone model show as
    # two distinct lines instead of collapsing into one.
    model: str
    # A key unique across this response, NOT necessarily a real Model.id -- a
    # primary (this item's own model) row uses the Item's id, a compatible
    # (secondary/"also fits") row uses the negative of the Model's id, so the two
    # spaces can never collide. Only used by the frontend as a stable React/
    # exclusion-set key, never round-tripped back to the API.
    model_id: int
    # Units currently on hand for this row -- the item's own StockLot.qty_remaining
    # sum for a primary row, or the summed qty_remaining of every item this model
    # is compatible with for a secondary row (it has no stock lots of its own).
    qty_remaining: Decimal


class StockListRead(BaseModel):
    entries: list[StockListEntryRead]
