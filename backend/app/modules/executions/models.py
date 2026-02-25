import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import BaseModel

if TYPE_CHECKING:
    from app.modules.delivery.models import DeliveryLog
    from app.modules.jobs.models import Job


class Execution(BaseModel):
    """
    Modelo de execucao do sistema.

    Representa uma execucao de um job (tarefa agendada), contendo
    o status, logs, dados extraidos, caminhos de screenshots e PDF.
    Herda de BaseModel (inclui id, created_at, updated_at).
    Execucoes sao registros permanentes — nao possuem soft delete.
    """

    __tablename__ = 'executions'

    # --- Chave estrangeira para o job ---
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('jobs.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )

    # --- Status da execucao ---
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default='pending',
    )

    # --- Logs e dados extraidos ---
    logs: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        default=None,
    )
    extracted_data: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
    )

    # --- Caminhos de artefatos no storage ---
    screenshots_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        default=None,
    )
    pdf_path: Mapped[str | None] = mapped_column(
        String(500),
        nullable=True,
        default=None,
    )

    # --- Flag de dry run ---
    is_dry_run: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    # --- Rastreamento Celery ---
    celery_task_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True,
        default=None,
        index=True,
    )

    # --- Heartbeat (prova de vida da execucao) ---
    last_heartbeat: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    # --- Timestamps de execucao ---
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )
    duration_seconds: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
        default=None,
    )

    # --- Relacionamentos ---
    job: Mapped['Job'] = relationship(
        'Job',
        back_populates='executions',
        lazy='selectin',
    )
    delivery_logs: Mapped[list['DeliveryLog']] = relationship(
        'DeliveryLog',
        back_populates='execution',
        lazy='selectin',
        foreign_keys='DeliveryLog.execution_id',
    )
