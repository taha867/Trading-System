from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base


class StockLot(Base):
    __tablename__ = "stock_lot"

    id: Mapped[int] = mapped_column(primary_key=True)
    purchase_order_line_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_order_line.id"), unique=True, index=True
    )
    item_id: Mapped[int] = mapped_column(ForeignKey("item.id"), index=True)
    qty_received: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    qty_remaining: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    landed_cost_pkr: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    received_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class StockMovement(Base):
    __tablename__ = "stock_movement"

    id: Mapped[int] = mapped_column(primary_key=True)
    stock_lot_id: Mapped[int] = mapped_column(ForeignKey("stock_lot.id"), index=True)
    movement_type: Mapped[str]
    qty_delta: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    reason: Mapped[str | None] = mapped_column(nullable=True)
    movement_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
