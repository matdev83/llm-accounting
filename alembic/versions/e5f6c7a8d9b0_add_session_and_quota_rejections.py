"""add session columns and quota_rejections table

Revision ID: e5f6c7a8d9b0
Revises: cc98ec5bdfa4
Create Date: 2025-07-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'e5f6c7a8d9b0'
down_revision: Union[str, None] = 'aa1b2c3d4e5f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('accounting_entries', schema=None) as batch_op:
        batch_op.add_column(sa.Column('session', sa.String(), nullable=True))
    with op.batch_alter_table('audit_log_entries', schema=None) as batch_op:
        batch_op.add_column(sa.Column('session', sa.String(), nullable=True))
    op.create_table(
        'quota_rejections',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('session', sa.String(), nullable=False),
        sa.Column('rejection_message', sa.String(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('quota_rejections')
    with op.batch_alter_table('audit_log_entries', schema=None) as batch_op:
        batch_op.drop_column('session')
    with op.batch_alter_table('accounting_entries', schema=None) as batch_op:
        batch_op.drop_column('session')
