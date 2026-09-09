from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.catalog.models import Item
from src.models import Base


class SalesOrder(Base):
    __tablename__ = "sales_order"

    id: Mapped[int] = mapped_column(primary_key=True)
    party_id: Mapped[int] = mapped_column(ForeignKey("party.id"), index=True)
    order_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

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
