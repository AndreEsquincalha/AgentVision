"""
Schemas Pydantic para o modulo de alertas.
"""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AlertRuleCreate(BaseModel):
    """Schema para criacao de uma regra de alerta."""

    name: str = Field(..., min_length=1, max_length=255, description='Nome da regra')
    description: str | None = Field(None, description='Descricao da regra')
    rule_type: str = Field(
        ...,
        description='Tipo da regra: failure_rate, duration_exceeded, worker_offline, token_budget',
    )
    conditions: dict = Field(
        default_factory=dict,
        description='Condicoes da regra (variam por tipo)',
    )
    severity: str = Field('warning', description='Severidade: info, warning, critical')
    notify_channel: str = Field('email', description='Canal: email ou webhook')
    notify_recipients: list[str] = Field(
        ...,
        min_length=1,
        description='Destinatarios (emails ou URLs de webhook)',
    )
    cooldown_minutes: int = Field(
        60,
        ge=1,
        le=1440,
        description='Cooldown em minutos entre alertas (1 a 1440)',
    )
    is_active: bool = Field(True, description='Se a regra esta ativa')

    @field_validator('rule_type')
    @classmethod
    def validate_rule_type(cls, v: str) -> str:
        """Valida tipo de regra."""
        allowed = ('failure_rate', 'duration_exceeded', 'worker_offline', 'token_budget')
        if v not in allowed:
            raise ValueError(f'Tipo invalido. Valores permitidos: {", ".join(allowed)}')
        return v

    @field_validator('severity')
    @classmethod
    def validate_severity(cls, v: str) -> str:
        """Valida severidade."""
        allowed = ('info', 'warning', 'critical')
        if v not in allowed:
            raise ValueError(f'Severidade invalida. Valores permitidos: {", ".join(allowed)}')
        return v

    @field_validator('notify_channel')
    @classmethod
    def validate_notify_channel(cls, v: str) -> str:
        """Valida canal de notificacao."""
        allowed = ('email', 'webhook')
        if v not in allowed:
            raise ValueError(f'Canal invalido. Valores permitidos: {", ".join(allowed)}')
        return v


class AlertRuleUpdate(BaseModel):
    """Schema para atualizacao de uma regra de alerta."""

    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None)
    conditions: dict | None = Field(None)
    severity: str | None = Field(None)
    notify_channel: str | None = Field(None)
    notify_recipients: list[str] | None = Field(None)
    cooldown_minutes: int | None = Field(None, ge=1, le=1440)
    is_active: bool | None = Field(None)

    @field_validator('severity')
    @classmethod
    def validate_severity(cls, v: str | None) -> str | None:
        if v is None:
            return v
        allowed = ('info', 'warning', 'critical')
        if v not in allowed:
            raise ValueError(f'Severidade invalida. Valores permitidos: {", ".join(allowed)}')
        return v

    @field_validator('notify_channel')
    @classmethod
    def validate_notify_channel(cls, v: str | None) -> str | None:
        if v is None:
            return v
        allowed = ('email', 'webhook')
        if v not in allowed:
            raise ValueError(f'Canal invalido. Valores permitidos: {", ".join(allowed)}')
        return v


class AlertRuleResponse(BaseModel):
    """Schema de resposta de regra de alerta."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None = None
    rule_type: str
    conditions: dict
    severity: str
    notify_channel: str
    notify_recipients: list[str]
    cooldown_minutes: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class AlertHistoryResponse(BaseModel):
    """Schema de resposta de historico de alertas."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rule_id: uuid.UUID
    rule_name: str
    rule_type: str
    severity: str
    message: str
    details: dict | None = None
    notified: bool
    notify_channel: str | None = None
    notify_error: str | None = None
    created_at: datetime
