from datetime import date, datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

from src.ledger.schemas import LedgerEntryRead
from src.pagination import PaginatedResponse
from src.sales.utils import money


class SalesOrderLineCreate(BaseModel):
    item_id: int
    qty: Annotated[Decimal, Field(gt=0, decimal_places=2)]
    rate_pkr: Annotated[Decimal, Field(gt=0, decimal_places=2)]


class SalesOrderCreate(BaseModel):
    party_id: int
    order_date: date
    invoice_number: Annotated[str, Field(max_length=64)] | None = None
    lines: Annotated[list[SalesOrderLineCreate], Field(min_length=1)]

    @field_validator("invoice_number", mode="before")
    @classmethod
    def blank_invoice_number_is_none(cls, value):
        # "no invoice number" has exactly one representation (NULL), so a blank or
        # whitespace-only form value can never become an unsearchable empty-string row.
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class SalesOrderLineLotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    stock_lot_id: int
    qty_consumed: Decimal
    unit_cost_pkr: Decimal
    lot_received_date: date  # when the lot this slice came from was received — shown on the sale's detail
    lot_item_id: int  # the item the lot belongs to: differs from the line's item when stock of an "also fits" item was used
    lot_item_sku: str


class SalesOrderLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    item_id: int
    qty: Decimal
    rate_pkr: Decimal
    consumptions: list[SalesOrderLineLotRead]
    # Embedded so a screen showing this line never needs a separate
    # id->name lookup fetch against the whole Items/Models/Categories catalog.
    item_sku: str
    item_variant: str | None = None
    model_name: str
    category_name: str

    @computed_field
    @property
    def amount_pkr(self) -> Decimal:
        return money(self.qty * self.rate_pkr)

    @computed_field
    @property
    def cost_pkr(self) -> Decimal:
        return money(sum((c.qty_consumed * c.unit_cost_pkr for c in self.consumptions), Decimal(0)))

    @computed_field
    @property
    def margin_pkr(self) -> Decimal:
        return money(self.amount_pkr - self.cost_pkr)


class SalesOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    shown_only: bool = False  # reference only: not in any balance, stock or profit figure
    party_id: int
    party_name: str  # embedded so no screen needs to download the parties list just to show a name
    order_date: date
    invoice_number: str | None = None
    created_at: datetime
    lines: list[SalesOrderLineRead]

    @computed_field
    @property
    def total_pkr(self) -> Decimal:
        return money(sum((line.amount_pkr for line in self.lines), Decimal(0)))

    @computed_field
    @property
    def total_margin_pkr(self) -> Decimal:
        return money(sum((line.margin_pkr for line in self.lines), Decimal(0)))


class SalesOrderDetailRead(SalesOrderRead):
    # The LedgerEntry rows this sale posted (reference_type="sales_order", reference_id=id) --
    # only on the single-sale endpoint, so the list stays light.
    ledger_entries: list[LedgerEntryRead]


class InvoiceNumberRead(BaseModel):
    id: int
    invoice_number: str | None


class InvoiceOptionRead(BaseModel):
    invoice_number: str
    sale_count: int  # invoice numbers are not unique — one number can cover several sales
    entry_count: int  # day-book entries (sales_log_exception, any kind) carrying this number


class LogExceptionInvoiceOptionRead(BaseModel):
    invoice_number: str
    entry_count: int  # how many "other entries" carry this number (a sale and its correction can share one)


class SalesLogExceptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    shown_only: bool = False  # reference only: not in any balance, stock or profit figure
    entry_date: date
    kind: str
    category_name: str | None
    qty: Decimal | None
    rate_pkr: Decimal | None
    amount_pkr: Decimal
    party_id: int | None
    party_name: str | None
    invoice_number: str | None
    note: str | None
    ledger_entry_id: int | None
    ledger_posted: bool
    created_at: datetime


class SalesLogExceptionKindTotalRead(BaseModel):
    kind: str
    count: int
    total_pkr: Decimal


class SalesLogExceptionListRead(PaginatedResponse[SalesLogExceptionRead]):
    total_amount_pkr: Decimal  # across every entry matching the filters, not just this page
    totals_by_kind: list[SalesLogExceptionKindTotalRead]


class SalesOrderListRead(PaginatedResponse[SalesOrderRead]):
    # Totals across every sale matching the current filters, not just the current page --
    # what the Sales Orders list's summary bar shows. With an item filter these are the
    # whole sales that contain that item, not just that item's lines.
    total_sales_pkr: Decimal
    total_margin_pkr: Decimal
    # Cancelled invoices (no items, no money — they can't be sales orders) matching the same
    # filters, so an invoice number picked from the dropdown is never a dead end. Capped; the
    # real count is cancelled_total. Always empty when an item filter is set (they have no item).
    cancelled_entries: list[SalesLogExceptionRead]
    cancelled_total: int


class InvoiceOrderRead(BaseModel):
    """One real sale inside an invoice (the full sale, its lots and ledger are on its own page)."""

    id: int
    order_date: date
    total_pkr: Decimal
    margin_pkr: Decimal


class InvoiceGroupRead(BaseModel):
    """One invoice: its sale(s) plus every day-book entry with the same number and customer. `total_pkr` is what the
    customer's ledger holds for it (booked + all entries); `no_stock_pkr` / `other_entries_pkr` are the parts that are
    not (yet) real sales, so not in profit."""

    group_key: str
    invoice_number: str | None
    party_id: int | None
    party_name: str | None
    invoice_date: date
    total_pkr: Decimal
    booked_pkr: Decimal  # the real sales
    margin_pkr: Decimal  # on the booked part only
    no_stock_pkr: Decimal  # lines that had no stock recorded ("No stock found")
    other_entries_pkr: Decimal  # bulk / no model / correction / discount
    is_cancelled: bool
    shown_only: bool = False  # every row of the invoice is reference-only (not in the summary totals)
    orders: list[InvoiceOrderRead]
    entries: list[SalesLogExceptionRead]


class InvoiceListRead(PaginatedResponse[InvoiceGroupRead]):
    # Across every invoice matching the filters, not just this page - the summary bar. `total` (from
    # PaginatedResponse) is the number of invoices.
    total_pkr: Decimal
    booked_pkr: Decimal
    margin_pkr: Decimal
    no_stock_pkr: Decimal
    other_entries_pkr: Decimal
    cancelled_count: int
