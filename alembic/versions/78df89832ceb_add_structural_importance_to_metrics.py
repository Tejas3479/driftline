"""add_structural_importance_to_metrics

Revision ID: 78df89832ceb
Revises: 93077cbbea2f
Create Date: 2026-07-21 13:06:03.429918

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '78df89832ceb'
down_revision: Union[str, Sequence[str], None] = '93077cbbea2f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


from sqlalchemy.dialects.postgresql import JSONB


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('metrics', sa.Column('structural_importance', JSONB(), server_default='[]', nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('metrics', 'structural_importance')
