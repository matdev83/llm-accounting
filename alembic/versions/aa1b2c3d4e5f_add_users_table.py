"""add users table

Revision ID: aa1b2c3d4e5f
Revises: f873f865a1ae
Create Date: 2025-07-01 00:00:01

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'aa1b2c3d4e5f'
down_revision: Union[str, None] = 'f873f865a1ae'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('user_name', sa.String(length=255), nullable=False, unique=True),
        sa.Column('ou_name', sa.String(length=255), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('last_enabled_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('last_disabled_at', sa.DateTime(), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=False, server_default=sa.text('1')),
    )


def downgrade() -> None:
    op.drop_table('users')
