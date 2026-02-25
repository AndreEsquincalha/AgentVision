"""add_execution_progress_and_job_notify

Adiciona campo progress_percent (Integer) na tabela executions para
rastreamento de progresso parcial (Sprint 11.3.2), e campo
notify_on_failure (Boolean) na tabela jobs para controle de
notificacoes em caso de falha (Sprint 11.3.4).

Revision ID: 011_progress_notify
Revises: 010_project_sandbox
Create Date: 2026-02-25

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '011_progress_notify'
down_revision: Union[str, None] = '010_project_sandbox'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Adiciona campo progress_percent na tabela executions (default 0)
    op.add_column(
        'executions',
        sa.Column(
            'progress_percent',
            sa.Integer(),
            nullable=False,
            server_default='0',
        ),
    )

    # Adiciona campo notify_on_failure na tabela jobs (default True)
    op.add_column(
        'jobs',
        sa.Column(
            'notify_on_failure',
            sa.Boolean(),
            nullable=False,
            server_default='true',
        ),
    )


def downgrade() -> None:
    op.drop_column('jobs', 'notify_on_failure')
    op.drop_column('executions', 'progress_percent')
