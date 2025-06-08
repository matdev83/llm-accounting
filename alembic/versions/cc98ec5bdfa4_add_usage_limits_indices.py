"""add indices to usage_limits columns

Revision ID: cc98ec5bdfa4
Revises: ba9718840e75
Create Date: 2025-06-08 20:21:20.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'cc98ec5bdfa4'
down_revision: Union[str, None] = 'ba9718840e75'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('usage_limits', schema=None) as batch_op:
        batch_op.create_index('ix_usage_limits_model', ['model'], unique=False)
        batch_op.create_index('ix_usage_limits_username', ['username'], unique=False)
        batch_op.create_index('ix_usage_limits_caller_name', ['caller_name'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('usage_limits', schema=None) as batch_op:
        batch_op.drop_index('ix_usage_limits_caller_name')
        batch_op.drop_index('ix_usage_limits_username')
        batch_op.drop_index('ix_usage_limits_model')
