"""add strategic indexes for performance optimization

Revision ID: 014
Revises: 013
Create Date: 2026-02-26
"""

from alembic import op
import sqlalchemy as sa

# revision identifiers
revision = '014'
down_revision = '013'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- executions: indice composto (job_id, status) ---
    # Otimiza queries de filtro por status dentro de um job
    op.create_index(
        'ix_executions_job_id_status',
        'executions',
        ['job_id', 'status'],
    )

    # --- executions: indice composto (job_id, created_at DESC) ---
    # Otimiza queries de execucoes recentes por job
    op.execute(sa.text(
        'CREATE INDEX ix_executions_job_id_created_at_desc '
        'ON executions (job_id, created_at DESC)'
    ))

    # --- jobs: indice composto (is_active, deleted_at) ---
    # Otimiza query de jobs ativos (is_active=True AND deleted_at IS NULL)
    op.create_index(
        'ix_jobs_is_active_deleted_at',
        'jobs',
        ['is_active', 'deleted_at'],
    )

    # --- delivery_logs: indice composto (execution_id, status) ---
    # Otimiza queries de status de entrega por execucao
    op.create_index(
        'ix_delivery_logs_execution_id_status',
        'delivery_logs',
        ['execution_id', 'status'],
    )


def downgrade() -> None:
    op.drop_index('ix_delivery_logs_execution_id_status', table_name='delivery_logs')
    op.drop_index('ix_jobs_is_active_deleted_at', table_name='jobs')
    op.drop_index('ix_executions_job_id_created_at_desc', table_name='executions')
    op.drop_index('ix_executions_job_id_status', table_name='executions')
