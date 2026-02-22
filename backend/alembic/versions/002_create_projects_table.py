"""create_projects_table

Revision ID: 002_create_projects
Revises: 001_create_users
Create Date: 2026-02-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '002_create_projects'
down_revision: Union[str, None] = '001_create_users'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Cria a tabela projects com todos os campos, indices e constraints."""
    op.create_table(
        'projects',
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
        # --- Campos basicos do projeto ---
        sa.Column(
            'name',
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            'base_url',
            sa.String(length=500),
            nullable=False,
        ),
        sa.Column(
            'description',
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            'encrypted_credentials',
            sa.Text(),
            nullable=True,
        ),
        # --- Configuracoes LLM ---
        sa.Column(
            'llm_provider',
            sa.String(length=50),
            nullable=False,
        ),
        sa.Column(
            'llm_model',
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            'encrypted_llm_api_key',
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            'llm_temperature',
            sa.Float(),
            nullable=False,
            server_default=sa.text('0.7'),
        ),
        sa.Column(
            'llm_max_tokens',
            sa.Integer(),
            nullable=False,
            server_default=sa.text('4096'),
        ),
        sa.Column(
            'llm_timeout',
            sa.Integer(),
            nullable=False,
            server_default=sa.text('120'),
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
    op.create_index('ix_projects_name', 'projects', ['name'])

    # Indice parcial para projetos ativos (otimiza consultas frequentes)
    op.create_index(
        'ix_projects_is_active',
        'projects',
        ['is_active'],
        postgresql_where=sa.text('deleted_at IS NULL'),
    )


def downgrade() -> None:
    """Remove a tabela projects e seus indices."""
    op.drop_index('ix_projects_is_active', table_name='projects')
    op.drop_index('ix_projects_name', table_name='projects')
    op.drop_table('projects')
