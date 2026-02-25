"""create_token_usage_table

Cria tabela token_usage para rastreamento de consumo de tokens LLM (Sprint 9.3).

Revision ID: 009_token_usage
Revises: 008_execution_controls
Create Date: 2026-02-24

"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '009_token_usage'
down_revision: Union[str, None] = '008_execution_controls'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'token_usage',
        sa.Column(
            'id',
            postgresql.UUID(as_uuid=True),
            nullable=False,
        ),
        sa.Column(
            'execution_id',
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey('executions.id', ondelete='CASCADE'),
            nullable=False,
            index=True,
        ),
        sa.Column('provider', sa.String(50), nullable=False),
        sa.Column('model', sa.String(100), nullable=False),
        sa.Column('input_tokens', sa.Integer(), default=0),
        sa.Column('output_tokens', sa.Integer(), default=0),
        sa.Column('total_tokens', sa.Integer(), default=0),
        sa.Column('image_count', sa.Integer(), default=0),
        sa.Column('estimated_cost_usd', sa.Float(), default=0.0),
        sa.Column(
            'created_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            'updated_at',
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint('id'),
    )

    # Indice composto para consultas de consumo por provider e periodo
    op.create_index(
        'ix_token_usage_provider_created_at',
        'token_usage',
        ['provider', 'created_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_token_usage_provider_created_at', table_name='token_usage')
    op.drop_table('token_usage')
