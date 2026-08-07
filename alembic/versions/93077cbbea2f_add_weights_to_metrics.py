"""add_weights_to_metrics

Revision ID: 93077cbbea2f
Revises: db622994a7d7
Create Date: 2026-07-21 11:40:17.402311

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '93077cbbea2f'
down_revision: str | Sequence[str] | None = 'db622994a7d7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('metrics', sa.Column('z_score_weight', sa.Float(), server_default='0.5', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('metrics', 'z_score_weight')
