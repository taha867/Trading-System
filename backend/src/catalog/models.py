from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models import Base


class Category(Base):
    __tablename__ = "category"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    is_active: Mapped[bool] = mapped_column(default=True)


class Brand(Base):
    __tablename__ = "brand"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(unique=True)
    is_active: Mapped[bool] = mapped_column(default=True)


class Model(Base):
    __tablename__ = "model"
    __table_args__ = (UniqueConstraint("brand_id", "name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brand.id"), index=True)
    name: Mapped[str]
    priority: Mapped[int] = mapped_column(default=0)
    is_active: Mapped[bool] = mapped_column(default=True)


class ItemCompatibleModel(Base):
    """Pure link table: an Item tagged as also fitting a Model beyond its primary model_id."""

    __tablename__ = "item_compatible_model"

    item_id: Mapped[int] = mapped_column(ForeignKey("item.id"), primary_key=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("model.id"), primary_key=True, index=True)


class Item(Base):
    __tablename__ = "item"

    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("category.id"), index=True)
    model_id: Mapped[int] = mapped_column(ForeignKey("model.id"), index=True)
    sku: Mapped[str] = mapped_column(unique=True)
    variant: Mapped[str | None] = mapped_column(nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)

    # One-directional — no Model.compatible_items back_populates; nothing needs that
    # direction yet. lazy="raise" per CLAUDE.md §2.5 — never lazy-load in async, every
    # read path must eager-load via selectinload.
    compatible_models: Mapped[list["Model"]] = relationship(
        secondary=ItemCompatibleModel.__table__,
        lazy="raise",
    )
