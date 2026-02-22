"""create_jobs_table

Revision ID: 003_create_jobs
Revises: 002_create_projects
Create Date: 2026-02-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '003_create_jobs'
down_revision: Union[str, None] = '002_create_projects'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Cria a tabela jobs com todos os campos, indices e constraints."""
    op.create_table(
        'jobs',
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
        # --- Chave estrangeira para o projeto ---
        sa.Column(
            'project_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('projects.id', ondelete='CASCADE'),
            nullable=False,
        ),
        # --- Campos basicos do job ---
        sa.Column(
            'name',
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            'cron_expression',
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            'agent_prompt',
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            'prompt_template_id',
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
        sa.Column(
            'execution_params',
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

    # Indice no campo name para buscas rapidas
    op.create_index('ix_jobs_name', 'jobs', ['name'])

    # Indice no campo project_id para buscas por projeto
    op.create_index('ix_jobs_project_id', 'jobs', ['project_id'])

    # Indice parcial para jobs ativos (otimiza consultas frequentes)
    op.create_index(
        'ix_jobs_is_active',
        'jobs',
        ['is_active'],
        postgresql_where=sa.text('deleted_at IS NULL'),
    )


def downgrade() -> None:
    """Remove a tabela jobs e seus indices."""
    op.drop_index('ix_jobs_is_active', table_name='jobs')
    op.drop_index('ix_jobs_project_id', table_name='jobs')
    op.drop_index('ix_jobs_name', table_name='jobs')
    op.drop_table('jobs')
