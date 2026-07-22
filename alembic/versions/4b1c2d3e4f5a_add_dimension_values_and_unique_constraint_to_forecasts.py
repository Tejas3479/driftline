"""add dimension values and unique constraint to forecasts

Revision ID: 4b1c2d3e4f5a
Revises: 78df89832ceb
Create Date: 2026-07-22 09:37:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '4b1c2d3e4f5a'
down_revision: Union[str, None] = '78df89832ceb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('forecasts', sa.Column('dimension_values', postgresql.JSONB(astext_type=sa.Text()), server_default='{}', nullable=False))
    op.create_unique_constraint('uq_forecasts_metric_dim_date_horizon', 'forecasts', ['metric_id', 'dimension_values', 'forecast_date', 'horizon_days'])


def downgrade() -> None:
    op.drop_constraint('uq_forecasts_metric_dim_date_horizon', 'forecasts', type_='unique')
    op.drop_column('forecasts', 'dimension_values')
