"""add_payments

Revision ID: b7a2e491f3c8
Revises: 943d3cd058b8
Create Date: 2026-08-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7a2e491f3c8'
down_revision: Union[str, Sequence[str], None] = '943d3cd058b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('payment_account',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('payment_method_id', sa.Integer(), nullable=False),
    sa.Column('label', sa.String(), nullable=False),
    sa.Column('account_number', sa.String(), nullable=True),
    sa.Column('opening_balance', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.ForeignKeyConstraint(['payment_method_id'], ['payment_method.id'], name=op.f('payment_account_payment_method_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('payment_account_pkey'))
    )
    op.create_index(op.f('payment_account_payment_method_id_idx'), 'payment_account', ['payment_method_id'], unique=False)

    op.create_table('payment_transaction',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('payment_account_id', sa.Integer(), nullable=False),
    sa.Column('direction', sa.String(), nullable=False),
    sa.Column('amount', sa.Numeric(precision=12, scale=2), nullable=False),
    sa.Column('transaction_date', sa.Date(), nullable=False),
    sa.Column('party_id', sa.Integer(), nullable=True),
    sa.Column('reference_type', sa.String(), nullable=True),
    sa.Column('reference_id', sa.Integer(), nullable=True),
    sa.Column('note', sa.String(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['party_id'], ['party.id'], name=op.f('payment_transaction_party_id_fkey')),
    sa.ForeignKeyConstraint(['payment_account_id'], ['payment_account.id'], name=op.f('payment_transaction_payment_account_id_fkey')),
    sa.PrimaryKeyConstraint('id', name=op.f('payment_transaction_pkey'))
    )
    op.create_index(op.f('payment_transaction_party_id_idx'), 'payment_transaction', ['party_id'], unique=False)
    op.create_index(op.f('payment_transaction_payment_account_id_idx'), 'payment_transaction', ['payment_account_id'], unique=False)

    op.add_column('ledger_entry', sa.Column('payment_account_id', sa.Integer(), nullable=True))
    op.create_index(op.f('ledger_entry_payment_account_id_idx'), 'ledger_entry', ['payment_account_id'], unique=False)
    op.create_foreign_key(op.f('ledger_entry_payment_account_id_fkey'), 'ledger_entry', 'payment_account', ['payment_account_id'], ['id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint(op.f('ledger_entry_payment_account_id_fkey'), 'ledger_entry', type_='foreignkey')
    op.drop_index(op.f('ledger_entry_payment_account_id_idx'), table_name='ledger_entry')
    op.drop_column('ledger_entry', 'payment_account_id')

    op.drop_index(op.f('payment_transaction_payment_account_id_idx'), table_name='payment_transaction')
    op.drop_index(op.f('payment_transaction_party_id_idx'), table_name='payment_transaction')
    op.drop_table('payment_transaction')

    op.drop_index(op.f('payment_account_payment_method_id_idx'), table_name='payment_account')
    op.drop_table('payment_account')
