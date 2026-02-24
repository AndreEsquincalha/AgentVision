"""add_fk_delivery_logs_execution_id

Revision ID: 9432b3f2cee4
Revises: 007_create_settings
Create Date: 2026-02-24 15:51:30.730780

"""
from typing import Sequence, Union

from alembic import op


# revision identifiers, used by Alembic.
revision: str = '9432b3f2cee4'
down_revision: Union[str, None] = '007_create_settings'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_foreign_key(
        'fk_delivery_logs_execution_id',
        'delivery_logs',
        'executions',
        ['execution_id'],
        ['id'],
        ondelete='CASCADE',
    )


def downgrade() -> None:
    op.drop_constraint('fk_delivery_logs_execution_id', 'delivery_logs', type_='foreignkey')
