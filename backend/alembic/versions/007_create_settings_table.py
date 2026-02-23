"""create_settings_table

Revision ID: 007_create_settings
Revises: 006_create_prompt_templates
Create Date: 2026-02-22

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '007_create_settings'
down_revision: Union[str, None] = '006_create_prompt_templates'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Cria a tabela settings com todos os campos, indices e constraints."""
    op.create_table(
        'settings',
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
        # --- Campos da configuracao ---
        sa.Column(
            'key',
            sa.String(length=255),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            'encrypted_value',
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            'category',
            sa.String(length=100),
            nullable=False,
        ),
        sa.Column(
            'description',
            sa.Text(),
            nullable=True,
        ),
        # --- Constraints ---
        sa.PrimaryKeyConstraint('id'),
    )

    # Indice no campo key para buscas rapidas (unique ja cria indice, mas explicitamos)
    op.create_index('ix_settings_key', 'settings', ['key'], unique=True)

    # Indice no campo category para filtros por categoria
    op.create_index('ix_settings_category', 'settings', ['category'])


def downgrade() -> None:
    """Remove a tabela settings e seus indices."""
    op.drop_index('ix_settings_category', table_name='settings')
    op.drop_index('ix_settings_key', table_name='settings')
    op.drop_table('settings')
