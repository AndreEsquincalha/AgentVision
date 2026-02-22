import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, Boolean
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import BaseModel, SoftDeleteModel

if TYPE_CHECKING:
    from app.modules.executions.models import Execution
    from app.modules.jobs.models import Job


class DeliveryConfig(SoftDeleteModel):
    """
    Modelo de configuracao de entrega do sistema.

    Define como os resultados de uma execucao serao entregues
    (email, webhook, etc.) para um job especifico.
    Herda de SoftDeleteModel (inclui id, created_at, updated_at, deleted_at).
    """

    __tablename__ = 'delivery_configs'

    # --- Chave estrangeira para o job ---
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('jobs.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )

    # --- Campos de configuracao ---
    channel_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    recipients: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
    )
    channel_config: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
    )

    # --- Status ---
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # --- Relacionamentos ---
    job: Mapped['Job'] = relationship(
        'Job',
        back_populates='delivery_configs',
    )
    delivery_logs: Mapped[list['DeliveryLog']] = relationship(
        'DeliveryLog',
        back_populates='delivery_config',
        lazy='selectin',
    )


class DeliveryLog(BaseModel):
    """
    Modelo de log de entrega do sistema.

    Registra o resultado de cada tentativa de entrega de um resultado
    de execucao atraves de um canal configurado.
    Herda de BaseModel (inclui id, created_at, updated_at).
    """

    __tablename__ = 'delivery_logs'

    # --- Chaves estrangeiras ---
    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    delivery_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('delivery_configs.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )

    # --- Campos do log ---
    channel_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default='pending',
    )
    error_message: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        default=None,
    )
    sent_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
    )

    # --- Relacionamentos ---
    delivery_config: Mapped['DeliveryConfig'] = relationship(
        'DeliveryConfig',
        back_populates='delivery_logs',
    )
    execution: Mapped['Execution'] = relationship(
        'Execution',
        back_populates='delivery_logs',
        foreign_keys=[execution_id],
    )
