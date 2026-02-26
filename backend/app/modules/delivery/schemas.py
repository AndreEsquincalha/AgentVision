import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.shared.security import (
    sanitize_email_recipient,
    sanitize_string_dict,
    validate_json_size,
)


class DeliveryConfigCreate(BaseModel):
    """Schema para criacao de uma configuracao de entrega."""

    job_id: uuid.UUID = Field(
        ...,
        description='ID do job associado',
    )
    channel_type: str = Field(
        ...,
        description='Tipo do canal de entrega (email, webhook)',
    )
    recipients: list[str] = Field(
        ...,
        min_length=1,
        description='Lista de destinatarios (emails, URLs, etc.)',
    )
    channel_config: dict | None = Field(
        None,
        description='Configuracoes especificas do canal (ex: assunto do email)',
    )
    is_active: bool = Field(
        True,
        description='Se a configuracao de entrega esta ativa',
    )
    max_retries: int = Field(
        3,
        ge=0,
        le=10,
        description='Numero maximo de retentativas automaticas',
    )
    retry_delay_seconds: int = Field(
        60,
        ge=10,
        le=3600,
        description='Delay base entre retentativas em segundos',
    )
    delivery_condition: str = Field(
        'always',
        description='Condicao para entrega (always, on_success, on_failure, on_change)',
    )
    email_template_id: uuid.UUID | None = Field(
        None,
        description='ID do template de email customizado',
    )

    @field_validator('delivery_condition')
    @classmethod
    def validate_delivery_condition(cls, v: str) -> str:
        """Valida que a condicao de entrega e suportada."""
        allowed = ('always', 'on_success', 'on_failure', 'on_change')
        if v.lower() not in allowed:
            raise ValueError(
                f'Condicao invalida. Valores permitidos: {", ".join(allowed)}'
            )
        return v.lower()

    @field_validator('channel_type')
    @classmethod
    def validate_channel_type(cls, v: str) -> str:
        """Valida que o tipo de canal e suportado."""
        allowed_types = ('email', 'webhook', 'slack', 'storage')
        if v.lower() not in allowed_types:
            raise ValueError(
                f'Tipo de canal invalido. Valores permitidos: {", ".join(allowed_types)}'
            )
        return v.lower()

    @field_validator('recipients')
    @classmethod
    def validate_recipients(cls, v: list[str]) -> list[str]:
        """Valida que a lista de destinatarios nao esta vazia e nao contem valores vazios."""
        cleaned = [sanitize_email_recipient(r) for r in v if r and r.strip()]
        if not cleaned:
            raise ValueError('A lista de destinatarios nao pode estar vazia')
        return cleaned

    @field_validator('channel_config')
    @classmethod
    def validate_channel_config_size(cls, v: dict | None) -> dict | None:
        """Valida tamanho maximo do JSON de configuracao."""
        sanitized = sanitize_string_dict(v) if v is not None else v
        return validate_json_size(sanitized, 50 * 1024, 'channel_config')


class DeliveryConfigUpdate(BaseModel):
    """Schema para atualizacao de uma configuracao de entrega. Todos os campos opcionais."""

    channel_type: str | None = Field(None)
    recipients: list[str] | None = Field(None, min_length=1)
    channel_config: dict | None = Field(None)
    is_active: bool | None = Field(None)
    max_retries: int | None = Field(None, ge=0, le=10)
    retry_delay_seconds: int | None = Field(None, ge=10, le=3600)
    delivery_condition: str | None = Field(None)
    email_template_id: uuid.UUID | None = Field(None)

    @field_validator('delivery_condition')
    @classmethod
    def validate_delivery_condition(cls, v: str | None) -> str | None:
        """Valida que a condicao de entrega e suportada (se fornecida)."""
        if v is None:
            return v
        allowed = ('always', 'on_success', 'on_failure', 'on_change')
        if v.lower() not in allowed:
            raise ValueError(
                f'Condicao invalida. Valores permitidos: {", ".join(allowed)}'
            )
        return v.lower()

    @field_validator('channel_type')
    @classmethod
    def validate_channel_type(cls, v: str | None) -> str | None:
        """Valida que o tipo de canal e suportado (se fornecido)."""
        if v is None:
            return v
        allowed_types = ('email', 'webhook', 'slack', 'storage')
        if v.lower() not in allowed_types:
            raise ValueError(
                f'Tipo de canal invalido. Valores permitidos: {", ".join(allowed_types)}'
            )
        return v.lower()

    @field_validator('recipients')
    @classmethod
    def validate_recipients(cls, v: list[str] | None) -> list[str] | None:
        """Valida que a lista de destinatarios nao contem valores vazios (se fornecida)."""
        if v is None:
            return v
        cleaned = [sanitize_email_recipient(r) for r in v if r and r.strip()]
        if not cleaned:
            raise ValueError('A lista de destinatarios nao pode estar vazia')
        return cleaned

    @field_validator('channel_config')
    @classmethod
    def validate_channel_config_size(cls, v: dict | None) -> dict | None:
        """Valida tamanho maximo do JSON de configuracao."""
        sanitized = sanitize_string_dict(v) if v is not None else v
        return validate_json_size(sanitized, 50 * 1024, 'channel_config')


class DeliveryConfigResponse(BaseModel):
    """Schema de resposta para configuracao de entrega."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    channel_type: str
    recipients: list[str] | None = None
    channel_config: dict | None = None
    is_active: bool
    max_retries: int = 3
    retry_delay_seconds: int = 60
    delivery_condition: str = 'always'
    email_template_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime


class DeliveryLogResponse(BaseModel):
    """Schema de resposta para log de entrega."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    execution_id: uuid.UUID
    delivery_config_id: uuid.UUID
    channel_type: str
    status: str
    error_message: str | None = None
    sent_at: datetime | None = None
    retry_count: int = 0
    next_retry_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
