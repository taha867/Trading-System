from decimal import Decimal

from sqlalchemy import Numeric, String
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.orm import Mapped, mapped_column

from src.models import Base


class Party(Base):
    __tablename__ = "party"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    contact: Mapped[str | None] = mapped_column(nullable=True)
    address: Mapped[str | None] = mapped_column(nullable=True)
    # postgresql.ARRAY (not generic sqlalchemy.ARRAY) so role-membership queries
    # (.contains()/.overlap(), needed from Phase 2 onward) work — the generic
    # type raises NotImplementedError/AttributeError for those comparators.
    # Whole-list reassignment only: neither ARRAY variant tracks in-place mutation.
    roles: Mapped[list[str]] = mapped_column(ARRAY(String))
    opening_balance: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=0)
    is_active: Mapped[bool] = mapped_column(default=True)
