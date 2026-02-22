import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


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

    @field_validator('channel_type')
    @classmethod
    def validate_channel_type(cls, v: str) -> str:
        """Valida que o tipo de canal e suportado."""
        allowed_types = ('email', 'webhook')
        if v.lower() not in allowed_types:
            raise ValueError(
                f'Tipo de canal invalido. Valores permitidos: {", ".join(allowed_types)}'
            )
        return v.lower()

    @field_validator('recipients')
    @classmethod
    def validate_recipients(cls, v: list[str]) -> list[str]:
        """Valida que a lista de destinatarios nao esta vazia e nao contem valores vazios."""
        cleaned = [r.strip() for r in v if r and r.strip()]
        if not cleaned:
            raise ValueError('A lista de destinatarios nao pode estar vazia')
        return cleaned


class DeliveryConfigUpdate(BaseModel):
    """Schema para atualizacao de uma configuracao de entrega. Todos os campos opcionais."""

    channel_type: str | None = Field(None)
    recipients: list[str] | None = Field(None, min_length=1)
    channel_config: dict | None = Field(None)
    is_active: bool | None = Field(None)

    @field_validator('channel_type')
    @classmethod
    def validate_channel_type(cls, v: str | None) -> str | None:
        """Valida que o tipo de canal e suportado (se fornecido)."""
        if v is None:
            return v
        allowed_types = ('email', 'webhook')
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
        cleaned = [r.strip() for r in v if r and r.strip()]
        if not cleaned:
            raise ValueError('A lista de destinatarios nao pode estar vazia')
        return cleaned


class DeliveryConfigResponse(BaseModel):
    """Schema de resposta para configuracao de entrega."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    channel_type: str
    recipients: list[str] | None = None
    channel_config: dict | None = None
    is_active: bool
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
    created_at: datetime
    updated_at: datetime
