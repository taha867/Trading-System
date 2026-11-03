"""add purchase search indexes and purchase_log_exception

Revision ID: c4e81b7a2d95
Revises: a3c7f1d95b28
Create Date: 2026-11-04 03:05:12.447319

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4e81b7a2d95'
down_revision: Union[str, Sequence[str], None] = 'a3c7f1d95b28'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # New table for purchases that can't become a PurchaseOrder (a category but no phone model):
    # only the money owed to the supplier is recorded, linked to its ledger entry. Mirrors
    # sales_log_exception. Empty at creation; the existing entries are backfilled by a separate
    # script, so this migration changes no data.
    op.create_table('purchase_log_exception',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('entry_date', sa.Date(), nullable=False),
    sa.Column('kind', sa.String(), nullable=False),
    sa.Column('party_id', sa.Integer(), nullable=False),
    sa.Column('category_name', sa.String(), nullable=True),
    sa.Column('qty', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('rate_pkr', sa.Numeric(precision=12, scale=2), nullable=True),
    sa.Column('amount_pkr', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('invoice_number', sa.String(), nullable=True),
    sa.Column('note', sa.String(), nullable=True),
    sa.Column('ledger_entry_id', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['ledger_entry_id'], ['ledger_entry.id'], name=op.f('purchase_log_exception_ledger_entry_id_fkey')),
    sa.ForeignKeyConstraint(['party_id'], ['party.id'], name=op.f('purchase_log_exception_party_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('purchase_log_exception_pkey'))
    )
    op.create_index(op.f('purchase_log_exception_entry_date_idx'), 'purchase_log_exception', ['entry_date'], unique=False)
    op.create_index(op.f('purchase_log_exception_party_id_idx'), 'purchase_log_exception', ['party_id'], unique=False)
    # Month filtering / newest-first ordering on the Purchase Orders screen, and exact
    # invoice-number lookups. Indexes only — no column or data change.
    op.create_index(op.f('purchase_order_order_date_idx'), 'purchase_order', ['order_date'], unique=False)
    op.create_index(op.f('purchase_order_invoice_number_idx'), 'purchase_order', ['invoice_number'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('purchase_order_invoice_number_idx'), table_name='purchase_order')
    op.drop_index(op.f('purchase_order_order_date_idx'), table_name='purchase_order')
    op.drop_index(op.f('purchase_log_exception_party_id_idx'), table_name='purchase_log_exception')
    op.drop_index(op.f('purchase_log_exception_entry_date_idx'), table_name='purchase_log_exception')
    op.drop_table('purchase_log_exception')
