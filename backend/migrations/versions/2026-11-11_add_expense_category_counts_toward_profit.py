"""add expense_category.counts_toward_profit

Revision ID: d7a2e94b1c60
Revises: c4e81b7a2d95
Create Date: 2026-11-11 16:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd7a2e94b1c60'
down_revision: Union[str, Sequence[str], None] = 'c4e81b7a2d95'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Schema only: every existing category keeps counting toward profit (default true). Which categories
    # stop counting (Personal) is a data change made by a separate, guarded one-off script.
    op.add_column(
        'expense_category',
        sa.Column('counts_toward_profit', sa.Boolean(), server_default=sa.text('true'), nullable=False),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('expense_category', 'counts_toward_profit')
