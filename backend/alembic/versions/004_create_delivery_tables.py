"""create_delivery_tables

Revision ID: 004_create_delivery
Revises: 003_create_jobs
Create Date: 2026-02-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '004_create_delivery'
down_revision: Union[str, None] = '003_create_jobs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Cria as tabelas delivery_configs e delivery_logs."""

    # --- Tabela delivery_configs ---
    op.create_table(
        'delivery_configs',
        # --- Campos herdados de BaseModel / SoftDeleteModel ---
        sa.Column(
            'id',
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text('gen_random_uuid()'),
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            'deleted_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        # --- Chave estrangeira para o job ---
        sa.Column(
            'job_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('jobs.id', ondelete='CASCADE'),
            nullable=False,
        ),
        # --- Campos de configuracao ---
        sa.Column(
            'channel_type',
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            'recipients',
            postgresql.JSON(),
            nullable=True,
        ),
        sa.Column(
            'channel_config',
            postgresql.JSON(),
            nullable=True,
        ),
        # --- Status ---
        sa.Column(
            'is_active',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('true'),
        ),
        # --- Constraints ---
        sa.PrimaryKeyConstraint('id'),
    )

    # Indice no campo job_id para buscas por job
    op.create_index('ix_delivery_configs_job_id', 'delivery_configs', ['job_id'])

    # --- Tabela delivery_logs ---
    op.create_table(
        'delivery_logs',
        # --- Campos herdados de BaseModel ---
        sa.Column(
            'id',
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text('gen_random_uuid()'),
        ),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        # --- Chaves estrangeiras ---
        sa.Column(
            'execution_id',
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            'delivery_config_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('delivery_configs.id', ondelete='CASCADE'),
            nullable=False,
        ),
        # --- Campos do log ---
        sa.Column(
            'channel_type',
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            'status',
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            'error_message',
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            'sent_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        # --- Constraints ---
        sa.PrimaryKeyConstraint('id'),
    )

    # Indices para buscas frequentes
    op.create_index(
        'ix_delivery_logs_execution_id',
        'delivery_logs',
        ['execution_id'],
    )
    op.create_index(
        'ix_delivery_logs_delivery_config_id',
        'delivery_logs',
        ['delivery_config_id'],
    )


def downgrade() -> None:
    """Remove as tabelas delivery_logs e delivery_configs e seus indices."""
    # Delivery logs (deve ser removida primeiro por causa das FKs)
    op.drop_index('ix_delivery_logs_delivery_config_id', table_name='delivery_logs')
    op.drop_index('ix_delivery_logs_execution_id', table_name='delivery_logs')
    op.drop_table('delivery_logs')

    # Delivery configs
    op.drop_index('ix_delivery_configs_job_id', table_name='delivery_configs')
    op.drop_table('delivery_configs')
