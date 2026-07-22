"""update forecast and accuracy log schemas

Revision ID: 5c2d3e4f5a6b
Revises: 4b1c2d3e4f5a
Create Date: 2026-07-22 16:35:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '5c2d3e4f5a6b'
down_revision: Union[str, None] = '4b1c2d3e4f5a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Update forecasts table
    op.drop_constraint('uq_forecasts_metric_dim_date_horizon', 'forecasts', type_='unique')
    op.add_column('forecasts', sa.Column('model_backend', sa.String(length=50), server_default='lightgbm', nullable=False))
    op.create_unique_constraint('uq_forecasts_metric_dim_date_horizon_backend', 'forecasts', ['metric_id', 'dimension_values', 'forecast_date', 'horizon_days', 'model_backend'])

    # Update forecast_accuracy_log table
    op.add_column('forecast_accuracy_log', sa.Column('horizon_days', sa.Integer(), server_default='7', nullable=False))
    op.add_column('forecast_accuracy_log', sa.Column('model_backend', sa.String(length=50), server_default='lightgbm', nullable=False))
    op.add_column('forecast_accuracy_log', sa.Column('predicted_p10', sa.Float(), nullable=True))
    op.add_column('forecast_accuracy_log', sa.Column('predicted_p90', sa.Float(), nullable=True))
    op.add_column('forecast_accuracy_log', sa.Column('abs_error', sa.Float(), server_default='0.0', nullable=False))
    op.alter_column('forecast_accuracy_log', 'abs_pct_error', existing_type=sa.Float(), nullable=True)
    op.add_column('forecast_accuracy_log', sa.Column('in_bounds', sa.Boolean(), nullable=True))
    op.add_column('forecast_accuracy_log', sa.Column('used_ml_model', sa.Boolean(), server_default='true', nullable=False))
    op.add_column('forecast_accuracy_log', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.create_index('ix_forecast_accuracy_metric_date', 'forecast_accuracy_log', ['metric_id', 'date'], unique=False)
    op.create_unique_constraint('uq_forecast_accuracy_log_metric_date_horizon_backend', 'forecast_accuracy_log', ['metric_id', 'date', 'horizon_days', 'model_backend'])


def downgrade() -> None:
    op.drop_constraint('uq_forecast_accuracy_log_metric_date_horizon_backend', 'forecast_accuracy_log', type_='unique')
    op.drop_index('ix_forecast_accuracy_metric_date', table_name='forecast_accuracy_log')
    op.drop_column('forecast_accuracy_log', 'created_at')
    op.drop_column('forecast_accuracy_log', 'used_ml_model')
    op.drop_column('forecast_accuracy_log', 'in_bounds')
    op.alter_column('forecast_accuracy_log', 'abs_pct_error', existing_type=sa.Float(), nullable=False)
    op.drop_column('forecast_accuracy_log', 'abs_error')
    op.drop_column('forecast_accuracy_log', 'predicted_p90')
    op.drop_column('forecast_accuracy_log', 'predicted_p10')
    op.drop_column('forecast_accuracy_log', 'model_backend')
    op.drop_column('forecast_accuracy_log', 'horizon_days')

    op.drop_constraint('uq_forecasts_metric_dim_date_horizon_backend', 'forecasts', type_='unique')
    op.drop_column('forecasts', 'model_backend')
    op.create_unique_constraint('uq_forecasts_metric_dim_date_horizon', 'forecasts', ['metric_id', 'dimension_values', 'forecast_date', 'horizon_days'])
