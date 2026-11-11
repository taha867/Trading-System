from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from src.ledger.schemas import LedgerEntryRead
from src.pagination import PaginatedResponse
from src.purchasing.constants import PurchaseOrderSource
from src.purchasing.utils import money


class ExchangeRateCreate(BaseModel):
    rate_date: date
    rate: Annotated[Decimal, Field(gt=0, decimal_places=4)]


class ExchangeRateRead(ExchangeRateCreate):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool


class ExchangeRateUpdate(BaseModel):
    rate: Annotated[Decimal, Field(gt=0, decimal_places=4)] | None = None


class PurchaseOrderLineCreate(BaseModel):
    item_id: int
    qty: Annotated[Decimal, Field(gt=0, decimal_places=2)]
    # Exactly one of these two is required, enforced by PurchaseOrderCreate's validator
    # against the order's own `source` — a china line prices in RMB (rate_pkr is derived
    # from that day's ExchangeRate), a local line is quoted directly in PKR.
    rate_rmb: Annotated[Decimal, Field(gt=0, decimal_places=2)] | None = None
    rate_pkr: Annotated[Decimal, Field(gt=0, decimal_places=2)] | None = None


class PurchaseOrderLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    qty: Decimal
    rate_rmb: Decimal | None = None
    rate_pkr: Decimal
    landed_cost_pkr: Decimal | None = None
    # Embedded so a screen showing this line never needs a separate
    # id->name lookup fetch against the whole Items/Models/Categories catalog.
    item_sku: str
    item_variant: str | None = None
    model_name: str
    category_name: str

    @computed_field
    @property
    def amount_rmb(self) -> Decimal | None:
        return money(self.qty * self.rate_rmb) if self.rate_rmb is not None else None

    @computed_field
    @property
    def amount_pkr(self) -> Decimal:
        return money(self.qty * self.rate_pkr)

    @computed_field
    @property
    def amount_landed_pkr(self) -> Decimal | None:
        return money(self.qty * self.landed_cost_pkr) if self.landed_cost_pkr is not None else None


class PurchaseOrderCreate(BaseModel):
    party_id: int
    order_date: date
    source: PurchaseOrderSource = "china"
    invoice_number: Annotated[str, Field(max_length=64)] | None = None
    lines: Annotated[list[PurchaseOrderLineCreate], Field(min_length=1)]

    @field_validator("invoice_number", mode="before")
    @classmethod
    def blank_invoice_number_is_none(cls, value):
        # "no invoice number" has exactly one representation (NULL), so a blank or
        # whitespace-only form value can never become an unsearchable empty-string row.
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value

    @model_validator(mode="after")
    def _validate_line_rates_match_source(self) -> "PurchaseOrderCreate":
        for i, line in enumerate(self.lines):
            if self.source == "china":
                if line.rate_rmb is None or line.rate_pkr is not None:
                    raise ValueError(f"line {i}: china-sourced lines must set rate_rmb, not rate_pkr")
            else:
                if line.rate_pkr is None or line.rate_rmb is not None:
                    raise ValueError(f"line {i}: non-china (local/mohsin) lines must set rate_pkr, not rate_rmb")
        return self


class PurchaseOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    party_id: int
    party_name: str  # embedded so no screen needs to download the parties list just to show a name
    order_date: date
    source: PurchaseOrderSource
    status: str
    invoice_number: str | None = None
    created_at: datetime
    lines: list[PurchaseOrderLineRead]

    @computed_field
    @property
    def total_rmb(self) -> Decimal | None:
        # None (not 0) when any line lacks an RMB rate — a real all-local order's total
        # isn't "zero RMB", it just isn't priced in RMB at all. Keyed on the lines' own
        # data, not on `source`, so a china order with one hand-fixed NULL rate_rmb line
        # can't crash this sum instead of just reporting itself as unpriced-in-RMB.
        amounts = [line.amount_rmb for line in self.lines]
        if any(amount is None for amount in amounts):
            return None
        return money(sum(amounts, Decimal(0)))

    @computed_field
    @property
    def total_pkr(self) -> Decimal:
        return money(sum((line.amount_pkr for line in self.lines), Decimal(0)))


class PurchaseLogExceptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entry_date: date
    kind: str
    party_id: int
    party_name: str
    category_name: str | None
    qty: Decimal | None
    rate_pkr: Decimal | None
    amount_pkr: Decimal
    invoice_number: str | None
    note: str | None
    ledger_entry_id: int | None
    ledger_posted: bool
    created_at: datetime


class PurchaseOrderListRead(PaginatedResponse[PurchaseOrderRead]):
    # Totals across every purchase order matching the current filters, not just the current page —
    # what the Purchase Orders list's summary bar shows. With an item filter these are the whole
    # orders that contain that item, not just that item's lines. total_rmb only counts lines that
    # were priced in RMB (china orders); it is 0 for an all-local selection.
    total_amount_pkr: Decimal
    total_rmb: Decimal


class PurchaseOrderLineDetailRead(PurchaseOrderLineRead):
    # What happened to this line after it was ordered — all null until it happens. Read from
    # StockLot (one per line, unique) and CargoAllocation (china lines only).
    stock_lot_id: int | None = None
    received_date: date | None = None
    qty_received: Decimal | None = None
    qty_remaining: Decimal | None = None
    cargo_shipment_id: int | None = None
    cargo_shipment_date: date | None = None
    allocated_cost_pkr: Decimal | None = None


class PurchaseOrderDetailRead(PurchaseOrderRead):
    # Only on the single-order endpoint, so the list stays light.
    lines: list[PurchaseOrderLineDetailRead]
    ledger_entries: list[LedgerEntryRead]  # the Accounts Payable row this order posted


class InvoiceNumberRead(BaseModel):
    id: int
    invoice_number: str | None


class InvoiceOptionRead(BaseModel):
    invoice_number: str
    order_count: int  # one supplier invoice can cover several purchase orders
    entry_count: int = 0  # payable-only entries (purchase_log_exception) carrying this number


class LogExceptionInvoiceOptionRead(BaseModel):
    invoice_number: str
    entry_count: int  # how many "other entries" carry this number


class PurchaseLogExceptionListRead(PaginatedResponse[PurchaseLogExceptionRead]):
    total_amount_pkr: Decimal  # across every entry matching the filters, not just this page


class PurchaseGroupOrderRead(BaseModel):
    """One real purchase order inside a row (the full order, lines, stock lots and ledger are on its own page)."""

    id: int
    order_date: date
    source: str
    status: str
    total_pkr: Decimal
    total_rmb: Decimal  # only lines priced in RMB (china orders); 0 for local / mohsin
    categories: list[str]


class PurchaseGroupRead(BaseModel):
    """One supplier invoice: its purchase order(s) plus every payable-only entry with the same number and vendor.
    `total_pkr` is what the ledger holds as payable for it (orders + entries)."""

    group_key: str
    invoice_number: str | None
    party_id: int
    party_name: str
    invoice_date: date
    total_pkr: Decimal
    orders_pkr: Decimal  # purchase orders with items (stock)
    entries_pkr: Decimal  # payable-only: owed to the supplier, no phone model, no stock
    total_rmb: Decimal
    categories: list[str]
    orders: list[PurchaseGroupOrderRead]
    entries: list[PurchaseLogExceptionRead]


class PurchaseGroupListRead(PaginatedResponse[PurchaseGroupRead]):
    # Across every row matching the filters, not just this page - the summary bar. `total` is the number of rows.
    total_pkr: Decimal
    orders_pkr: Decimal
    entries_pkr: Decimal
    total_rmb: Decimal
