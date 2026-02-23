"""create_prompt_templates_table

Revision ID: 006_create_prompt_templates
Revises: 005_create_executions
Create Date: 2026-02-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '006_create_prompt_templates'
down_revision: Union[str, None] = '005_create_executions'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Cria a tabela prompt_templates com todos os campos, indices e constraints."""
    op.create_table(
        'prompt_templates',
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
        # --- Campos do template ---
        sa.Column(
            'name',
            sa.String(length=255),
            nullable=False,
        ),
        sa.Column(
            'content',
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            'description',
            sa.Text(),
            nullable=True,
        ),
        sa.Column(
            'category',
            sa.String(length=100),
            nullable=True,
        ),
        sa.Column(
            'version',
            sa.Integer(),
            nullable=False,
            server_default=sa.text('1'),
        ),
        # --- Constraints ---
        sa.PrimaryKeyConstraint('id'),
    )

    # Indice no campo name para buscas rapidas
    op.create_index('ix_prompt_templates_name', 'prompt_templates', ['name'])

    # Indice no campo category para filtros por categoria
    op.create_index('ix_prompt_templates_category', 'prompt_templates', ['category'])


def downgrade() -> None:
    """Remove a tabela prompt_templates e seus indices."""
    op.drop_index('ix_prompt_templates_category', table_name='prompt_templates')
    op.drop_index('ix_prompt_templates_name', table_name='prompt_templates')
    op.drop_table('prompt_templates')
