from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

POSTGRES_INDEXES_NAMING_CONVENTION = {
    "ix": "%(column_0_label)s_idx",
    "uq": "%(table_name)s_%(column_0_name)s_key",
    "ck": "%(table_name)s_%(constraint_name)s_check",
    "fk": "%(table_name)s_%(column_0_name)s_fkey",
    "pk": "%(table_name)s_pkey",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=POSTGRES_INDEXES_NAMING_CONVENTION)


class Setting(Base):
    """App-wide settings, singleton row (id=1, get-or-create — see src/settings.py).
    No domain owns this table, which is why it lives here rather than in a
    dedicated package (planned since PLAN.md's Phase 0 entity list)."""

    __tablename__ = "setting"

    id: Mapped[int] = mapped_column(primary_key=True)
    shop_name: Mapped[str | None] = mapped_column(nullable=True)
    shop_address: Mapped[str | None] = mapped_column(nullable=True)
