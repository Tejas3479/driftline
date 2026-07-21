"""add_weights_to_metrics

Revision ID: 93077cbbea2f
Revises: db622994a7d7
Create Date: 2026-07-21 11:40:17.402311

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '93077cbbea2f'
down_revision: Union[str, Sequence[str], None] = 'db622994a7d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('metrics', sa.Column('z_score_weight', sa.Float(), server_default='0.5', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('metrics', 'z_score_weight')
