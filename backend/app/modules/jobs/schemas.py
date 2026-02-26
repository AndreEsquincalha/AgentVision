import uuid
from datetime import datetime

from enum import Enum

from croniter import croniter
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.shared.schemas import PaginatedResponse
from app.shared.security import (
    mask_sensitive_dict,
    sanitize_email_recipient,
    sanitize_name,
    sanitize_string_dict,
    sanitize_text,
    validate_json_size,
)
from app.shared.utils import decrypt_dict


class JobPriority(str, Enum):
    """Enum de prioridade de jobs."""

    low = 'low'
    normal = 'normal'
    high = 'high'


class DeliveryConfigInline(BaseModel):
    """Schema inline para configuracao de entrega ao criar um job."""

    channel_type: str = Field(
        ...,
        description='Tipo do canal de entrega (email, webhook)',
    )
    recipients: list[str] = Field(
        ...,
        min_length=1,
        description='Lista de destinatarios',
    )
    channel_config: dict | None = Field(
        None,
        description='Configuracoes especificas do canal',
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
    def sanitize_recipients(cls, v: list[str]) -> list[str]:
        """Remove CR/LF e espacos dos destinatarios."""
        cleaned = [sanitize_email_recipient(r) for r in v if r and r.strip()]
        if not cleaned:
            raise ValueError('A lista de destinatarios nao pode estar vazia')
        return cleaned

    @field_validator('channel_config')
    @classmethod
    def sanitize_channel_config(cls, v: dict | None) -> dict | None:
        """Sanitiza configuracoes do canal."""
        sanitized = sanitize_string_dict(v) if v is not None else v
        return validate_json_size(sanitized, 50 * 1024, 'channel_config')


class JobCreate(BaseModel):
    """Schema para criacao de um novo job."""

    project_id: uuid.UUID = Field(
        ...,
        description='ID do projeto associado',
    )
    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description='Nome do job',
    )
    cron_expression: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description='Expressao cron para agendamento (ex: "0 8 * * *")',
    )
    agent_prompt: str = Field(
        ...,
        min_length=1,
        description='Prompt enviado ao agente de automacao',
    )
    prompt_template_id: uuid.UUID | None = Field(
        None,
        description='ID do template de prompt (opcional)',
    )
    execution_params: dict | None = Field(
        None,
        description='Parametros adicionais de execucao (JSON)',
    )
    priority: JobPriority = Field(
        JobPriority.normal,
        description='Prioridade do job (low, normal, high)',
    )
    notify_on_failure: bool = Field(
        True,
        description='Se deve notificar em caso de falha na execucao',
    )
    delivery_configs: list[DeliveryConfigInline] | None = Field(
        None,
        description='Configuracoes de entrega a serem criadas junto com o job',
    )

    @field_validator('name')
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        """Valida que o nome nao esta vazio."""
        if not v or not v.strip():
            raise ValueError('O nome do job nao pode estar vazio')
        return sanitize_name(v)

    @field_validator('cron_expression')
    @classmethod
    def validate_cron_expression(cls, v: str) -> str:
        """Valida que a expressao cron tem formato valido."""
        if not croniter.is_valid(v):
            raise ValueError(
                'Expressao cron invalida. Use formato padrao '
                '(ex: "0 8 * * *" para todo dia as 8h)'
            )
        return sanitize_text(v)

    @field_validator('agent_prompt')
    @classmethod
    def prompt_not_empty(cls, v: str) -> str:
        """Valida que o prompt do agente nao esta vazio."""
        if not v or not v.strip():
            raise ValueError('O prompt do agente nao pode estar vazio')
        return sanitize_text(v)

    @field_validator('execution_params')
    @classmethod
    def validate_execution_params_size(cls, v: dict | None) -> dict | None:
        """Valida tamanho maximo do JSON de parametros."""
        sanitized = sanitize_string_dict(v) if v is not None else v
        return validate_json_size(sanitized, 50 * 1024, 'execution_params')


class JobUpdate(BaseModel):
    """Schema para atualizacao de um job. Todos os campos sao opcionais."""

    name: str | None = Field(None, min_length=1, max_length=255)
    cron_expression: str | None = Field(None, min_length=1, max_length=100)
    agent_prompt: str | None = Field(None, min_length=1)
    prompt_template_id: uuid.UUID | None = Field(None)
    execution_params: dict | None = Field(None)
    priority: JobPriority | None = Field(
        None,
        description='Prioridade do job (low, normal, high)',
    )
    notify_on_failure: bool | None = Field(
        None,
        description='Se deve notificar em caso de falha na execucao',
    )
    is_active: bool | None = Field(None)

    @field_validator('name')
    @classmethod
    def name_not_empty(cls, v: str | None) -> str | None:
        """Valida que o nome nao esta vazio (se fornecido)."""
        if v is not None and not v.strip():
            raise ValueError('O nome do job nao pode estar vazio')
        return sanitize_name(v) if v is not None else v

    @field_validator('cron_expression')
    @classmethod
    def validate_cron_expression(cls, v: str | None) -> str | None:
        """Valida que a expressao cron tem formato valido (se fornecida)."""
        if v is None:
            return v
        if not croniter.is_valid(v):
            raise ValueError(
                'Expressao cron invalida. Use formato padrao '
                '(ex: "0 8 * * *" para todo dia as 8h)'
            )
        return sanitize_text(v)

    @field_validator('agent_prompt')
    @classmethod
    def prompt_not_empty(cls, v: str | None) -> str | None:
        """Valida que o prompt do agente nao esta vazio (se fornecido)."""
        if v is not None and not v.strip():
            raise ValueError('O prompt do agente nao pode estar vazio')
        return sanitize_text(v) if v is not None else v

    @field_validator('execution_params')
    @classmethod
    def validate_execution_params_size(cls, v: dict | None) -> dict | None:
        """Valida tamanho maximo do JSON de parametros."""
        sanitized = sanitize_string_dict(v) if v is not None else v
        return validate_json_size(sanitized, 50 * 1024, 'execution_params')


class JobToggle(BaseModel):
    """Schema para ativar/desativar um job."""

    is_active: bool = Field(
        ...,
        description='Novo status do job (true=ativo, false=inativo)',
    )


class DeliveryConfigResponse(BaseModel):
    """Schema de resposta para configuracao de entrega vinculada ao job."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    channel_type: str
    recipients: list[str] | None = None
    channel_config: dict | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class JobResponse(BaseModel):
    """
    Schema de resposta com dados do job.

    Inclui o nome do projeto associado e as configuracoes de entrega.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    project_name: str | None = None
    name: str
    cron_expression: str
    agent_prompt: str
    prompt_template_id: uuid.UUID | None = None
    execution_params: dict | None = None
    priority: str = 'normal'
    notify_on_failure: bool = True
    is_active: bool
    next_execution: datetime | None = None
    delivery_configs: list[DeliveryConfigResponse] = []
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, job: 'Job', next_execution: datetime | None = None) -> 'JobResponse':
        """
        Cria um JobResponse a partir de um modelo Job.

        Inclui o nome do projeto e calcula a proxima execucao.
        """
        # Converte delivery_configs do modelo para schemas de resposta
        delivery_config_responses = []
        if hasattr(job, 'delivery_configs') and job.delivery_configs:
            for dc in job.delivery_configs:
                if dc.deleted_at is not None:
                    continue
                decrypted = None
                if dc.channel_config:
                    try:
                        decrypted = decrypt_dict(dc.channel_config)
                    except Exception:
                        decrypted = None
                masked = mask_sensitive_dict(decrypted) if decrypted else None
                delivery_config_responses.append(
                    DeliveryConfigResponse(
                        id=dc.id,
                        job_id=dc.job_id,
                        channel_type=dc.channel_type,
                        recipients=dc.recipients,
                        channel_config=masked,
                        is_active=dc.is_active,
                        created_at=dc.created_at,
                        updated_at=dc.updated_at,
                    )
                )

        # Acessa campos com seguranca (podem nao existir em migracoes pendentes)
        priority: str = getattr(job, 'priority', 'normal') or 'normal'
        notify_on_failure: bool = getattr(job, 'notify_on_failure', True)
        if notify_on_failure is None:
            notify_on_failure = True

        return cls(
            id=job.id,
            project_id=job.project_id,
            project_name=job.project.name if job.project else None,
            name=job.name,
            cron_expression=job.cron_expression,
            agent_prompt=job.agent_prompt,
            prompt_template_id=job.prompt_template_id,
            execution_params=job.execution_params,
            priority=priority,
            notify_on_failure=notify_on_failure,
            is_active=job.is_active,
            next_execution=next_execution,
            delivery_configs=delivery_config_responses,
            created_at=job.created_at,
            updated_at=job.updated_at,
        )


class DryRunResponse(BaseModel):
    """Schema de resposta para dry run de um job."""

    model_config = ConfigDict(from_attributes=True)

    job_id: uuid.UUID
    job_name: str
    status: str = 'pending'
    is_dry_run: bool = True
    message: str


# Alias para resposta paginada de jobs
JobListResponse = PaginatedResponse[JobResponse]
