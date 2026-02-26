"""add security hardening tables and user role

Revision ID: 012_add_security_hardening
Revises: 011_add_execution_progress_and_job_notify
Create Date: 2026-02-25 17:30:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

import json

from app.shared.utils import encrypt_dict


# revision identifiers, used by Alembic.
revision = '012_add_security_hardening'
down_revision = '011_add_execution_progress_and_job_notify'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # users.role
    op.add_column(
        'users',
        sa.Column('role', sa.String(length=20), server_default='admin', nullable=False),
    )
    op.alter_column('users', 'role', server_default=None)

    # token_blacklist
    op.create_table(
        'token_blacklist',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('jti', sa.String(length=64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_token_blacklist_jti', 'token_blacklist', ['jti'], unique=True)
    op.create_index('ix_token_blacklist_expires_at', 'token_blacklist', ['expires_at'], unique=False)

    # audit_log
    op.create_table(
        'audit_log',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.String(length=50), nullable=False),
        sa.Column('resource_type', sa.String(length=100), nullable=False),
        sa.Column('resource_id', sa.String(length=100), nullable=True),
        sa.Column('details', postgresql.JSON(), nullable=True),
        sa.Column('ip_address', sa.String(length=45), nullable=True),
    )
    op.create_index('ix_audit_log_user_id', 'audit_log', ['user_id'], unique=False)
    op.create_index('ix_audit_log_action', 'audit_log', ['action'], unique=False)
    op.create_index('ix_audit_log_resource_type', 'audit_log', ['resource_type'], unique=False)
    op.create_index('ix_audit_log_resource_id', 'audit_log', ['resource_id'], unique=False)

    # delivery_configs.channel_config: JSON -> Text
    op.alter_column(
        'delivery_configs',
        'channel_config',
        existing_type=postgresql.JSON(),
        type_=sa.Text(),
        postgresql_using='channel_config::text',
        existing_nullable=True,
    )

    # Recriptografa channel_config existente
    bind = op.get_bind()
    rows = bind.execute(
        sa.text('SELECT id, channel_config FROM delivery_configs WHERE channel_config IS NOT NULL')
    ).fetchall()
    for row in rows:
        config_id = row[0]
        raw_value = row[1]
        if not raw_value:
            continue
        try:
            parsed = json.loads(raw_value)
        except Exception:
            # Ja pode estar criptografado
            continue
        if not isinstance(parsed, dict):
            continue
        encrypted = encrypt_dict(parsed)
        bind.execute(
            sa.text('UPDATE delivery_configs SET channel_config = :val WHERE id = :id'),
            {'val': encrypted, 'id': str(config_id)},
        )


def downgrade() -> None:
    # Reverte channel_config para JSON (sem recriptografar)
    op.alter_column(
        'delivery_configs',
        'channel_config',
        existing_type=sa.Text(),
        type_=postgresql.JSON(),
        postgresql_using='channel_config::json',
        existing_nullable=True,
    )

    op.drop_index('ix_audit_log_resource_id', table_name='audit_log')
    op.drop_index('ix_audit_log_resource_type', table_name='audit_log')
    op.drop_index('ix_audit_log_action', table_name='audit_log')
    op.drop_index('ix_audit_log_user_id', table_name='audit_log')
    op.drop_table('audit_log')

    op.drop_index('ix_token_blacklist_expires_at', table_name='token_blacklist')
    op.drop_index('ix_token_blacklist_jti', table_name='token_blacklist')
    op.drop_table('token_blacklist')

    op.drop_column('users', 'role')
