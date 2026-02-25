"""add_project_sandbox_fields

Adiciona campos de sandbox (allowed_domains e blocked_urls) na tabela projects
para controle de seguranca do agente de navegacao (Sprint 10.2.1).

Revision ID: 010_project_sandbox
Revises: 009_token_usage
Create Date: 2026-02-25

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '010_project_sandbox'
down_revision: Union[str, None] = '009_token_usage'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Adiciona campo allowed_domains (JSON, nullable)
    # Lista de dominios permitidos para navegacao do agente
    op.add_column(
        'projects',
        sa.Column(
            'allowed_domains',
            postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
        ),
    )

    # Adiciona campo blocked_urls (JSON, nullable)
    # Lista de padroes regex de URLs bloqueadas
    op.add_column(
        'projects',
        sa.Column(
            'blocked_urls',
            postgresql.JSON(astext_type=sa.Text()),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column('projects', 'blocked_urls')
    op.drop_column('projects', 'allowed_domains')
