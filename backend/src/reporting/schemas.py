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


class StockListRead(BaseModel):
    entries: list[StockListEntryRead]
