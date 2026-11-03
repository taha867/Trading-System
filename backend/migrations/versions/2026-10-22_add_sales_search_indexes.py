"""add sales search indexes

Revision ID: a3c7f1d95b28
Revises: d1e54e52c664
Create Date: 2026-10-22 11:20:41.318204

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a3c7f1d95b28'
down_revision: Union[str, Sequence[str], None] = 'd1e54e52c664'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Month filtering / newest-first ordering on the Sales Orders screen, exact invoice-number
    # lookups, and the "Other entries" list's date and customer filters. Indexes only — no
    # column or data change.
    op.create_index(op.f('sales_order_order_date_idx'), 'sales_order', ['order_date'], unique=False)
    op.create_index(op.f('sales_order_invoice_number_idx'), 'sales_order', ['invoice_number'], unique=False)
    op.create_index(op.f('sales_log_exception_entry_date_idx'), 'sales_log_exception', ['entry_date'], unique=False)
    op.create_index(op.f('sales_log_exception_party_id_idx'), 'sales_log_exception', ['party_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('sales_log_exception_party_id_idx'), table_name='sales_log_exception')
    op.drop_index(op.f('sales_log_exception_entry_date_idx'), table_name='sales_log_exception')
    op.drop_index(op.f('sales_order_invoice_number_idx'), table_name='sales_order')
    op.drop_index(op.f('sales_order_order_date_idx'), table_name='sales_order')
