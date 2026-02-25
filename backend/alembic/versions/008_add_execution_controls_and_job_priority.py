"""add_execution_controls_and_job_priority

Adiciona campos para controle de execucoes (Sprint 8):
- executions.celery_task_id: correlacao com task Celery
- executions.last_heartbeat: prova de vida da execucao
- jobs.priority: prioridade do job (low, normal, high)

Revision ID: 008_execution_controls
Revises: 9432b3f2cee4
Create Date: 2026-02-24

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = '008_execution_controls'
down_revision: Union[str, None] = '9432b3f2cee4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- executions.celery_task_id ---
    op.add_column(
        'executions',
        sa.Column('celery_task_id', sa.String(255), nullable=True),
    )
    op.create_index(
        'ix_executions_celery_task_id',
        'executions',
        ['celery_task_id'],
    )

    # --- executions.last_heartbeat ---
    op.add_column(
        'executions',
        sa.Column('last_heartbeat', sa.DateTime(timezone=True), nullable=True),
    )

    # --- jobs.priority ---
    op.add_column(
        'jobs',
        sa.Column(
            'priority',
            sa.String(20),
            nullable=False,
            server_default='normal',
        ),
    )


def downgrade() -> None:
    op.drop_column('jobs', 'priority')
    op.drop_column('executions', 'last_heartbeat')
    op.drop_index('ix_executions_celery_task_id', table_name='executions')
    op.drop_column('executions', 'celery_task_id')
