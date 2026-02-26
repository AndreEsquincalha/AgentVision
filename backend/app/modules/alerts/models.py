"""
Modelos de alertas do AgentVision.

Define regras de alerta configuraveis e historico de alertas disparados.
"""

import uuid

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import BaseModel, SoftDeleteModel


class AlertRule(SoftDeleteModel):
    """
    Regra de alerta configuravel.

    Define condicoes que, quando atendidas, disparam notificacoes
    via email ou webhook.
    """

    __tablename__ = 'alert_rules'

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
    rule_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        index=True,
    )  # failure_rate, duration_exceeded, worker_offline, token_budget
    conditions: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )
    # Exemplo de conditions por tipo:
    # failure_rate: {"threshold_pct": 50, "last_n_executions": 10, "job_id": null}
    # duration_exceeded: {"max_minutes": 30, "job_id": null}
    # worker_offline: {}
    # token_budget: {"max_tokens_per_day": 1000000, "max_cost_per_day_usd": 10.0}

    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default='warning',
    )  # info, warning, critical

    notify_channel: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default='email',
    )  # email, webhook
    notify_recipients: Mapped[list] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )  # ["admin@example.com"] ou ["https://webhook.site/..."]

    cooldown_minutes: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=60,
    )

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )


class AlertHistory(BaseModel):
    """
    Historico de alertas disparados.

    Registra cada vez que uma regra e avaliada e um alerta e enviado.
    """

    __tablename__ = 'alert_history'

    rule_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    rule_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    rule_type: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    severity: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
    )
    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    details: Mapped[dict | None] = mapped_column(
        JSON,
        nullable=True,
    )
    notified: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )
    notify_channel: Mapped[str | None] = mapped_column(
        String(20),
        nullable=True,
    )
    notify_error: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )
