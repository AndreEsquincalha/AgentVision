"""create executions archive table

Revision ID: 015
Revises: 014
Create Date: 2026-02-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSON

# revision identifiers
revision = '015'
down_revision = '014'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'executions_archive',
        sa.Column('id', UUID(as_uuid=True), primary_key=True),
        sa.Column('job_id', UUID(as_uuid=True), nullable=False, index=True),
        sa.Column('status', sa.String(20), nullable=False),
        sa.Column('logs_compressed', sa.LargeBinary(), nullable=True),
        sa.Column('extracted_data_compressed', sa.LargeBinary(), nullable=True),
        sa.Column('screenshots_path', sa.String(500), nullable=True),
        sa.Column('pdf_path', sa.String(500), nullable=True),
        sa.Column('progress_percent', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('is_dry_run', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('celery_task_id', sa.String(255), nullable=True),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('finished_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('archived_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Indice para busca por periodo de criacao
    op.create_index(
        'ix_executions_archive_created_at',
        'executions_archive',
        ['created_at'],
    )


def downgrade() -> None:
    op.drop_index('ix_executions_archive_created_at', table_name='executions_archive')
    op.drop_table('executions_archive')
