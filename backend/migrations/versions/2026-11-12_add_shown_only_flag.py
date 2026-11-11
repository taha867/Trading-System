"""add shown_only flag to sales/purchase/expense/payment records

Revision ID: e3b91c5d7a28
Revises: d7a2e94b1c60
Create Date: 2026-11-12 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e3b91c5d7a28'
down_revision: Union[str, Sequence[str], None] = 'd7a2e94b1c60'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TABLES = ('sales_order', 'sales_log_exception', 'purchase_order', 'purchase_log_exception', 'expense', 'payment_transaction')


def upgrade() -> None:
    """Upgrade schema. Schema only: nothing is flagged here (a separate guarded one-off script flags 3 Sept 2026)."""
    for table in TABLES:
        op.add_column(table, sa.Column('shown_only', sa.Boolean(), server_default=sa.text('false'), nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    for table in reversed(TABLES):
        op.drop_column(table, 'shown_only')
