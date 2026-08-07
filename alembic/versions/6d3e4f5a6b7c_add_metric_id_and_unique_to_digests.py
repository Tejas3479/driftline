"""add metric_id and unique constraint to digests

Revision ID: 6d3e4f5a6b7c
Revises: 5c2d3e4f5a6b
Create Date: 2026-07-23 11:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '6d3e4f5a6b7c'
down_revision: str | None = '5c2d3e4f5a6b'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('digests', sa.Column('metric_id', sa.Integer(), sa.ForeignKey('metrics.id', ondelete='CASCADE'), nullable=True))
    op.create_unique_constraint('uq_digests_workspace_metric_period', 'digests', ['workspace_id', 'metric_id', 'period_start', 'period_end'])


def downgrade() -> None:
    op.drop_constraint('uq_digests_workspace_metric_period', 'digests', type_='unique')
    op.drop_column('digests', 'metric_id')
