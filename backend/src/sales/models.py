from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.catalog.models import Item
from src.inventory.models import StockLot
from src.models import Base
from src.parties.models import Party


class SalesOrder(Base):
    __tablename__ = "sales_order"

    id: Mapped[int] = mapped_column(primary_key=True)
    party_id: Mapped[int] = mapped_column(ForeignKey("party.id"), index=True)
    # Indexed: the Sales Orders screen filters by month and sorts newest-first on this.
    order_date: Mapped[date] = mapped_column(Date, index=True)
    # Optional — Shakeel's own invoice number from the day book, kept only for
    # cross-referencing against paper records; never used as a key. Deliberately NOT
    # unique: a day-book correction/discount (SalesLogException) reuses its sale's number.
    invoice_number: Mapped[str | None] = mapped_column(nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Read-only navigation so SalesOrderRead can embed the customer's name instead of every
    # screen downloading the whole parties list — every read path must joinedload it
    # (SALES_ORDER_LOAD_OPTIONS), same lazy="raise" discipline as `lines` below.
    party: Mapped["Party"] = relationship(lazy="raise")

    @property
    def party_name(self) -> str:
        return self.party.name

    lines: Mapped[list["SalesOrderLine"]] = relationship(
        back_populates="sales_order",
        cascade="all, delete-orphan",
        order_by="SalesOrderLine.id",
        lazy="raise",  # CLAUDE.md §2.5: never lazy-load in async — turns a miss into a named error
    )


class SalesOrderLine(Base):
    __tablename__ = "sales_order_line"

    id: Mapped[int] = mapped_column(primary_key=True)
    sales_order_id: Mapped[int] = mapped_column(ForeignKey("sales_order.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("item.id"), index=True)
    qty: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    rate_pkr: Mapped[Decimal] = mapped_column(Numeric(12, 2))

    sales_order: Mapped["SalesOrder"] = relationship(back_populates="lines", lazy="raise")
    consumptions: Mapped[list["SalesOrderLineLot"]] = relationship(
        back_populates="sales_order_line",
        cascade="all, delete-orphan",
        order_by="SalesOrderLineLot.id",
        lazy="raise",
    )
    # Read-only navigation for display purposes (SalesOrderLineRead embeds the
    # item's sku/model/category), same shape as purchasing/models.py's PurchaseOrderLine.
    item: Mapped["Item"] = relationship(lazy="raise")

    @property
    def item_sku(self) -> str:
        return self.item.sku

    @property
    def item_variant(self) -> str | None:
        return self.item.variant

    @property
    def model_name(self) -> str:
        return self.item.model.name

    @property
    def category_name(self) -> str:
        return self.item.category.name


class SalesOrderLineLot(Base):
    __tablename__ = "sales_order_line_lot"

    id: Mapped[int] = mapped_column(primary_key=True)
    sales_order_line_id: Mapped[int] = mapped_column(ForeignKey("sales_order_line.id"), index=True)
    stock_lot_id: Mapped[int] = mapped_column(ForeignKey("stock_lot.id"), index=True)
    qty_consumed: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    unit_cost_pkr: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    sales_order_line: Mapped["SalesOrderLine"] = relationship(back_populates="consumptions", lazy="raise")
    # Read-only navigation for display (the lot's received date) — joinedload it wherever
    # SalesOrderLineLotRead is serialized (SALES_ORDER_LOAD_OPTIONS).
    stock_lot: Mapped["StockLot"] = relationship(lazy="raise")

    @property
    def lot_received_date(self) -> date:
        return self.stock_lot.received_date


class SalesLogException(Base):
    """A sale-like event that cannot become a real SalesOrder because it has no
    specific item (a bulk/mixed-model batch, a price correction/discount with no
    product attached) or carries no real value (a cancelled invoice, kept only so
    the invoice-number sequence doesn't look like it has an unexplained gap).

    Deliberately outside the SalesOrder/SalesOrderLine/StockLot chain: `qty` and
    `category_name` are recorded for audit ("how many pieces, what category, not
    deducted from stock") but never touch inventory. When real money moves,
    `ledger_entry_id` points at the one LedgerEntry posted for it directly (see
    scripts/import_daybook_sept2026_stage2.py) -- a cancelled invoice (amount 0)
    has no ledger entry at all.
    """

    __tablename__ = "sales_log_exception"

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_date: Mapped[date] = mapped_column(Date, index=True)
    # "cancelled_invoice" | "bulk_mixed_models" | "blank_model" | "correction" | "discount"
    kind: Mapped[str]
    category_name: Mapped[str | None] = mapped_column(nullable=True)
    qty: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    rate_pkr: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    amount_pkr: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    party_id: Mapped[int | None] = mapped_column(ForeignKey("party.id"), nullable=True, index=True)
    invoice_number: Mapped[str | None] = mapped_column(nullable=True)
    note: Mapped[str | None] = mapped_column(nullable=True)
    ledger_entry_id: Mapped[int | None] = mapped_column(ForeignKey("ledger_entry.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Read-only navigation for the "Other entries" list — joinedload it in every read path.
    party: Mapped["Party | None"] = relationship(lazy="raise")

    @property
    def party_name(self) -> str | None:
        return self.party.name if self.party is not None else None

    @property
    def ledger_posted(self) -> bool:
        # A cancelled invoice (amount 0) never posted a ledger row.
        return self.ledger_entry_id is not None
