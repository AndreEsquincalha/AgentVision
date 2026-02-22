import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import SoftDeleteModel

if TYPE_CHECKING:
    from app.modules.delivery.models import DeliveryConfig
    from app.modules.projects.models import Project


class Job(SoftDeleteModel):
    """
    Modelo de job (tarefa agendada) do sistema.

    Representa uma tarefa de automacao vinculada a um projeto,
    com expressao cron para agendamento, prompt do agente e
    parametros de execucao.
    Herda de SoftDeleteModel (inclui id, created_at, updated_at, deleted_at).
    """

    __tablename__ = 'jobs'

    # --- Chave estrangeira para o projeto ---
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('projects.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )

    # --- Campos basicos ---
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    cron_expression: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    agent_prompt: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    prompt_template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        default=None,
    )
    execution_params: Mapped[dict | None] = mapped_column(
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
    project: Mapped['Project'] = relationship(
        'Project',
        back_populates='jobs',
        lazy='selectin',
    )
    delivery_configs: Mapped[list['DeliveryConfig']] = relationship(
        'DeliveryConfig',
        back_populates='job',
        lazy='selectin',
        cascade='all, delete-orphan',
    )
