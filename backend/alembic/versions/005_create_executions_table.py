"""create_executions_table

Revision ID: 005_create_executions
Revises: 004_create_delivery
Create Date: 2026-02-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '005_create_executions'
down_revision: Union[str, None] = '004_create_delivery'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Cria a tabela executions e adiciona FK em delivery_logs."""

    # --- Tabela executions ---
    op.create_table(
        'executions',
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
        # --- Chave estrangeira para o job ---
        sa.Column(
            'job_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('jobs.id', ondelete='CASCADE'),
            nullable=False,
        ),
        # --- Status ---
        sa.Column(
            'status',
            sa.String(length=20),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        # --- Logs e dados extraidos ---
        sa.Column(
            'logs',
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            'extracted_data',
            postgresql.JSON(),
            nullable=True,
        ),
        # --- Caminhos de artefatos ---
        sa.Column(
            'screenshots_path',
            sa.String(length=500),
            nullable=True,
        ),
        sa.Column(
            'pdf_path',
            sa.String(length=500),
            nullable=True,
        ),
        # --- Flag de dry run ---
        sa.Column(
            'is_dry_run',
            sa.Boolean(),
            nullable=False,
            server_default=sa.text('false'),
        ),
        # --- Timestamps de execucao ---
        sa.Column(
            'started_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            'finished_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            'duration_seconds',
            sa.Integer(),
            nullable=True,
        ),
        # --- Constraints ---
        sa.PrimaryKeyConstraint('id'),
    )

    # Indices para buscas frequentes
    op.create_index('ix_executions_job_id', 'executions', ['job_id'])
    op.create_index('ix_executions_status', 'executions', ['status'])
    op.create_index('ix_executions_created_at', 'executions', ['created_at'])

    # --- Adiciona FK de delivery_logs.execution_id para executions.id ---
    # A coluna execution_id ja existe em delivery_logs (criada na migration 004),
    # mas sem constraint de FK. Agora que a tabela executions existe, adicionamos.
    op.create_foreign_key(
        'fk_delivery_logs_execution_id',
        'delivery_logs',
        'executions',
        ['execution_id'],
        ['id'],
        ondelete='CASCADE',
    )


def downgrade() -> None:
    """Remove a FK de delivery_logs e a tabela executions."""

    # Remove a FK de delivery_logs.execution_id
    op.drop_constraint(
        'fk_delivery_logs_execution_id',
        'delivery_logs',
        type_='foreignkey',
    )

    # Remove indices e tabela executions
    op.drop_index('ix_executions_created_at', table_name='executions')
    op.drop_index('ix_executions_status', table_name='executions')
    op.drop_index('ix_executions_job_id', table_name='executions')
    op.drop_table('executions')
