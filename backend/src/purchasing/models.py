from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.catalog.models import Item
from src.models import Base
from src.parties.models import Party


class ExchangeRate(Base):
    __tablename__ = "exchange_rate"

    id: Mapped[int] = mapped_column(primary_key=True)
    rate_date: Mapped[date] = mapped_column(Date, unique=True)
    rate: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    is_active: Mapped[bool] = mapped_column(default=True)


class PurchaseOrder(Base):
    __tablename__ = "purchase_order"

    id: Mapped[int] = mapped_column(primary_key=True)
    party_id: Mapped[int] = mapped_column(ForeignKey("party.id"), index=True)
    # Indexed: the Purchase Orders screen filters by month and sorts newest-first on this.
    order_date: Mapped[date] = mapped_column(Date, index=True)
    source: Mapped[str] = mapped_column(default="china", server_default="china")
    status: Mapped[str] = mapped_column(default="draft")
    # Optional — a vendor's own invoice/receipt number, kept only for cross-referencing
    # against paper records (e.g. the day-book catch-up import); never used as a key.
    # Deliberately NOT unique: one supplier invoice can cover several purchase orders.
    invoice_number: Mapped[str | None] = mapped_column(nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Read-only navigation so PurchaseOrderRead can embed the vendor's name instead of every
    # screen downloading the whole parties list — every read path must joinedload it
    # (PURCHASE_ORDER_LOAD_OPTIONS), same lazy="raise" discipline as `lines` below.
    party: Mapped["Party"] = relationship(lazy="raise")

    @property
    def party_name(self) -> str:
        return self.party.name

    lines: Mapped[list["PurchaseOrderLine"]] = relationship(
        back_populates="purchase_order",
        cascade="all, delete-orphan",
        order_by="PurchaseOrderLine.id",
        lazy="raise",  # CLAUDE.md §2.5: never lazy-load in async — turns a miss into a named error
    )


class PurchaseOrderLine(Base):
    __tablename__ = "purchase_order_line"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_order_id: Mapped[int] = mapped_column(ForeignKey("purchase_order.id"), index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("item.id"), index=True)
    qty: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    rate_rmb: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    rate_pkr: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    landed_cost_pkr: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)

    purchase_order: Mapped["PurchaseOrder"] = relationship(back_populates="lines", lazy="raise")
    # Read-only navigation for display purposes (PurchaseOrderLineRead embeds the
    # item's sku/model/category) — purchasing still only references Item by id,
    # doesn't own it; no back_populates, Item has no reason to know about this.
    # Every read path must joinedload the whole chain (item -> model, item -> category),
    # same lazy="raise" discipline as the relationship itself.
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


class PurchaseLogException(Base):
    """A purchase that cannot become a real PurchaseOrder because the day book gave a category but
    no phone model (e.g. "TPU 540 pcs", "Borderless") — so no specific Item/StockLot can exist.

    Deliberately outside the PurchaseOrder/PurchaseOrderLine/StockLot chain: only the money owed to
    the supplier is recorded (one Accounts Payable LedgerEntry, linked by `ledger_entry_id`), and
    `category_name`/`qty`/`rate_pkr` are kept for audit ("what and how many, not added to stock").
    Mirrors sales.models.SalesLogException.
    """

    __tablename__ = "purchase_log_exception"

    id: Mapped[int] = mapped_column(primary_key=True)
    entry_date: Mapped[date] = mapped_column(Date, index=True)
    kind: Mapped[str]  # "no_model" — see constants.PurchaseLogExceptionKind
    party_id: Mapped[int] = mapped_column(ForeignKey("party.id"), index=True)
    category_name: Mapped[str | None] = mapped_column(nullable=True)
    qty: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    rate_pkr: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    amount_pkr: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    invoice_number: Mapped[str | None] = mapped_column(nullable=True)
    note: Mapped[str | None] = mapped_column(nullable=True)
    ledger_entry_id: Mapped[int | None] = mapped_column(ForeignKey("ledger_entry.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Read-only navigation for the "Other entries" list — joinedload it in every read path.
    party: Mapped["Party"] = relationship(lazy="raise")

    @property
    def party_name(self) -> str:
        return self.party.name

    @property
    def ledger_posted(self) -> bool:
        return self.ledger_entry_id is not None
