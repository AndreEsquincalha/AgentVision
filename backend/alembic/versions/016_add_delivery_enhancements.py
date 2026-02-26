"""Adiciona campos de retry, condicao de entrega e template de email.

Campos adicionados em delivery_configs:
- max_retries: Numero maximo de retentativas automaticas
- retry_delay_seconds: Delay base entre retentativas (segundos)
- delivery_condition: Condicao para entrega (always, on_success, on_failure, on_change)
- email_template_id: Referencia para template de email customizado

Campos adicionados em delivery_logs:
- retry_count: Numero da tentativa atual
- next_retry_at: Timestamp da proxima retentativa agendada

Revision ID: 016
Revises: 015
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers
revision = '016'
down_revision = '015'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- delivery_configs: campos de retry e condicao ---
    op.add_column(
        'delivery_configs',
        sa.Column(
            'max_retries',
            sa.Integer(),
            nullable=False,
            server_default='3',
        ),
    )
    op.add_column(
        'delivery_configs',
        sa.Column(
            'retry_delay_seconds',
            sa.Integer(),
            nullable=False,
            server_default='60',
        ),
    )
    op.add_column(
        'delivery_configs',
        sa.Column(
            'delivery_condition',
            sa.String(20),
            nullable=False,
            server_default='always',
        ),
    )
    op.add_column(
        'delivery_configs',
        sa.Column(
            'email_template_id',
            UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        'fk_delivery_configs_email_template_id',
        'delivery_configs',
        'prompt_templates',
        ['email_template_id'],
        ['id'],
        ondelete='SET NULL',
    )

    # --- delivery_logs: campos de retry ---
    op.add_column(
        'delivery_logs',
        sa.Column(
            'retry_count',
            sa.Integer(),
            nullable=False,
            server_default='0',
        ),
    )
    op.add_column(
        'delivery_logs',
        sa.Column(
            'next_retry_at',
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )


def downgrade() -> None:
    # delivery_logs
    op.drop_column('delivery_logs', 'next_retry_at')
    op.drop_column('delivery_logs', 'retry_count')

    # delivery_configs
    op.drop_constraint(
        'fk_delivery_configs_email_template_id',
        'delivery_configs',
        type_='foreignkey',
    )
    op.drop_column('delivery_configs', 'email_template_id')
    op.drop_column('delivery_configs', 'delivery_condition')
    op.drop_column('delivery_configs', 'retry_delay_seconds')
    op.drop_column('delivery_configs', 'max_retries')
