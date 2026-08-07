"""initial_schema

Revision ID: c3cbb107211d
Revises: 
Create Date: 2026-07-21 03:22:13.219362

"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c3cbb107211d'
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Declare PostgreSQL ENUM types with create_type=False so table creation does not trigger duplicate DDL
direction_good_enum = postgresql.ENUM('up_is_good', 'down_is_good', name='direction_good_enum', create_type=False)
sensitivity_enum = postgresql.ENUM('low', 'medium', 'high', name='sensitivity_enum', create_type=False)
grain_enum = postgresql.ENUM('daily', 'weekly', name='grain_enum', create_type=False)
anomaly_type_enum = postgresql.ENUM('spike', 'dip', 'level_shift', 'volatility', name='anomaly_type_enum', create_type=False)
anomaly_status_enum = postgresql.ENUM('new', 'reviewed', 'resolved', 'false_positive', name='anomaly_status_enum', create_type=False)


def upgrade() -> None:
    """Upgrade schema."""
    # Ensure ENUM types exist before creating tables
    direction_good_enum.create(op.get_bind(), checkfirst=True)
    sensitivity_enum.create(op.get_bind(), checkfirst=True)
    grain_enum.create(op.get_bind(), checkfirst=True)
    anomaly_type_enum.create(op.get_bind(), checkfirst=True)
    anomaly_status_enum.create(op.get_bind(), checkfirst=True)

    op.create_table('workspaces',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('digests',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('period_start', sa.Date(), nullable=False),
        sa.Column('period_end', sa.Date(), nullable=False),
        sa.Column('pdf_path', sa.String(length=512), nullable=False),
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('metrics',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('unit', sa.String(length=50), nullable=True),
        sa.Column('direction_good', direction_good_enum, nullable=False),
        sa.Column('sensitivity', sensitivity_enum, nullable=False),
        sa.Column('grain', grain_enum, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('users',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('role', sa.String(length=50), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    op.create_table('alert_rules',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('metric_id', sa.Integer(), nullable=False),
        sa.Column('min_severity', sa.Float(), nullable=False),
        sa.Column('channels', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(['metric_id'], ['metrics.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('anomalies',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('metric_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('severity_score', sa.Float(), nullable=False),
        sa.Column('type', anomaly_type_enum, nullable=False),
        sa.Column('z_score', sa.Float(), nullable=False),
        sa.Column('isolation_score', sa.Float(), nullable=False),
        sa.Column('status', anomaly_status_enum, server_default='new', nullable=False),
        sa.Column('explanation_text', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['metric_id'], ['metrics.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_anomalies_metric_date', 'anomalies', ['metric_id', 'date'], unique=False)
    op.create_table('daily_rollups',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('metric_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('value_total', sa.Float(), nullable=False),
        sa.Column('trend', sa.Float(), nullable=True),
        sa.Column('seasonal', sa.Float(), nullable=True),
        sa.Column('residual', sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(['metric_id'], ['metrics.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_daily_rollups_metric_date', 'daily_rollups', ['metric_id', 'date'], unique=False)
    op.create_table('dimension_defs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('metric_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(['metric_id'], ['metrics.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('forecast_accuracy_log',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('metric_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('predicted_p50', sa.Float(), nullable=False),
        sa.Column('actual', sa.Float(), nullable=False),
        sa.Column('abs_pct_error', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['metric_id'], ['metrics.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('forecasts',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('metric_id', sa.Integer(), nullable=False),
        sa.Column('forecast_date', sa.Date(), nullable=False),
        sa.Column('horizon_days', sa.Integer(), nullable=False),
        sa.Column('p10', sa.Float(), nullable=False),
        sa.Column('p50', sa.Float(), nullable=False),
        sa.Column('p90', sa.Float(), nullable=False),
        sa.Column('model_version', sa.String(length=100), nullable=False),
        sa.Column('generated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['metric_id'], ['metrics.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_forecasts_metric_date', 'forecasts', ['metric_id', 'forecast_date'], unique=False)
    op.create_table('observations',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('metric_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('dimension_values', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('value', sa.Float(), nullable=False),
        sa.ForeignKeyConstraint(['metric_id'], ['metrics.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('ix_observations_metric_date', 'observations', ['metric_id', 'date'], unique=False)
    op.create_table('anomaly_drivers',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('anomaly_id', sa.Integer(), nullable=False),
        sa.Column('dimension_name', sa.String(length=255), nullable=False),
        sa.Column('dimension_value', sa.String(length=255), nullable=False),
        sa.Column('contribution_value', sa.Float(), nullable=False),
        sa.Column('contribution_pct', sa.Float(), nullable=False),
        sa.Column('rank', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['anomaly_id'], ['anomalies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('anomaly_drivers')
    op.drop_index('ix_observations_metric_date', table_name='observations')
    op.drop_table('observations')
    op.drop_index('ix_forecasts_metric_date', table_name='forecasts')
    op.drop_table('forecasts')
    op.drop_table('forecast_accuracy_log')
    op.drop_table('dimension_defs')
    op.drop_index('ix_daily_rollups_metric_date', table_name='daily_rollups')
    op.drop_table('daily_rollups')
    op.drop_index('ix_anomalies_metric_date', table_name='anomalies')
    op.drop_table('anomalies')
    op.drop_table('alert_rules')
    op.drop_table('users')
    op.drop_table('metrics')
    op.drop_table('digests')
    op.drop_table('workspaces')

    # Drop ENUM types explicitly
    anomaly_status_enum.drop(op.get_bind(), checkfirst=True)
    anomaly_type_enum.drop(op.get_bind(), checkfirst=True)
    grain_enum.drop(op.get_bind(), checkfirst=True)
    sensitivity_enum.drop(op.get_bind(), checkfirst=True)
    direction_good_enum.drop(op.get_bind(), checkfirst=True)
