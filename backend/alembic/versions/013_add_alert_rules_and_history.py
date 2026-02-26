"""add alert rules and history tables

Revision ID: 013
Revises: 012
Create Date: 2026-02-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

# revision identifiers
revision = '013'
down_revision = '012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'alert_rules',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('rule_type', sa.String(50), nullable=False, index=True),
        sa.Column('conditions', JSON(), nullable=False, server_default='{}'),
        sa.Column('severity', sa.String(20), nullable=False, server_default='warning'),
        sa.Column('notify_channel', sa.String(20), nullable=False, server_default='email'),
        sa.Column('notify_recipients', JSON(), nullable=False, server_default='[]'),
        sa.Column('cooldown_minutes', sa.Integer(), nullable=False, server_default='60'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    )

    op.create_table(
        'alert_history',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('rule_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('rule_name', sa.String(255), nullable=False),
        sa.Column('rule_type', sa.String(50), nullable=False),
        sa.Column('severity', sa.String(20), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('details', JSON(), nullable=True),
        sa.Column('notified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('notify_channel', sa.String(20), nullable=True),
        sa.Column('notify_error', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table('alert_history')
    op.drop_table('alert_rules')
