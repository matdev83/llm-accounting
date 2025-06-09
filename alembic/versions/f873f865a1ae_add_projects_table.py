"""add projects table

Revision ID: f873f865a1ae
Revises: cc98ec5bdfa4
Create Date: 2025-07-01 00:00:00

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'f873f865a1ae'
down_revision: Union[str, None] = 'cc98ec5bdfa4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'projects',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(), nullable=False, unique=True)
    )


def downgrade() -> None:
    op.drop_table('projects')
