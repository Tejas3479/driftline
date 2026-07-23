"""create notifications table

Revision ID: 7e4f5a6b7c8d
Revises: 6d3e4f5a6b7c
Create Date: 2026-07-23 16:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '7e4f5a6b7c8d'
down_revision: Union[str, None] = '6d3e4f5a6b7c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'notifications',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('workspace_id', sa.Integer(), nullable=False),
        sa.Column('metric_id', sa.Integer(), nullable=False),
        sa.Column('anomaly_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('severity_score', sa.Float(), nullable=False),
        sa.Column('is_read', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['workspace_id'], ['workspaces.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['metric_id'], ['metrics.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['anomaly_id'], ['anomalies.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('anomaly_id')
    )
    op.create_index('ix_notifications_workspace_created', 'notifications', ['workspace_id', 'created_at'], unique=False)
    op.create_unique_constraint('uq_alert_rules_metric_id', 'alert_rules', ['metric_id'])


def downgrade() -> None:
    op.drop_constraint('uq_alert_rules_metric_id', 'alert_rules', type_='unique')
    op.drop_index('ix_notifications_workspace_created', table_name='notifications')
    op.drop_table('notifications')
