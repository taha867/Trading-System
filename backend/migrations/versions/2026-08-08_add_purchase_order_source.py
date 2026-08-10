"""add_purchase_order_source

Revision ID: 943d3cd058b8
Revises: f5f369972f38
Create Date: 2026-08-08 19:16:00.625377

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '943d3cd058b8'
down_revision: Union[str, Sequence[str], None] = 'f5f369972f38'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "purchase_order",
        sa.Column("source", sa.String(), nullable=False, server_default="china"),
    )
    op.alter_column(
        "purchase_order_line",
        "rate_rmb",
        existing_type=sa.Numeric(precision=12, scale=2),
        nullable=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Will raise an IntegrityError if any local-sourced purchase order line exists with
    # rate_rmb NULL — expected: downgrading past this point requires resolving those
    # rows by hand first, since a NULL rate_rmb has no meaningful RMB value to backfill.
    op.alter_column(
        "purchase_order_line",
        "rate_rmb",
        existing_type=sa.Numeric(precision=12, scale=2),
        nullable=False,
    )
    op.drop_column("purchase_order", "source")
