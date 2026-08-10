from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base


class CargoMode(Base):
    __tablename__ = "cargo_mode"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    is_active: Mapped[bool] = mapped_column(default=True)


class CargoCostBasis(Base):
    __tablename__ = "cargo_cost_basis"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    code: Mapped[str] = mapped_column(unique=True)  # "weight" | "cbm" | "piece" — service branches on this, not name
    is_active: Mapped[bool] = mapped_column(default=True)


class CargoShipment(Base):
    __tablename__ = "cargo_shipment"

    id: Mapped[int] = mapped_column(primary_key=True)
    cargo_agent_id: Mapped[int] = mapped_column(ForeignKey("party.id"), index=True)
    cargo_mode_id: Mapped[int] = mapped_column(ForeignKey("cargo_mode.id"), index=True)
    cost_basis_id: Mapped[int] = mapped_column(ForeignKey("cargo_cost_basis.id"), index=True)
    shipment_date: Mapped[date] = mapped_column(Date)
    total_cost_pkr: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    allocations: Mapped[list["CargoAllocation"]] = relationship(
        back_populates="cargo_shipment",
        cascade="all, delete-orphan",
        order_by="CargoAllocation.id",
        lazy="raise",  # CLAUDE.md §2.5: never lazy-load in async — turns a miss into a named error
    )


class CargoAllocation(Base):
    __tablename__ = "cargo_allocation"

    id: Mapped[int] = mapped_column(primary_key=True)
    cargo_shipment_id: Mapped[int] = mapped_column(ForeignKey("cargo_shipment.id"), index=True)
    purchase_order_line_id: Mapped[int] = mapped_column(
        ForeignKey("purchase_order_line.id"), unique=True, index=True
    )
    basis_value: Mapped[Decimal] = mapped_column(Numeric(12, 4))
    allocated_cost_pkr: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    cargo_shipment: Mapped["CargoShipment"] = relationship(back_populates="allocations", lazy="raise")
