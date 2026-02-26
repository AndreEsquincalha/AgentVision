import uuid
from datetime import datetime
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.shared.schemas import PaginatedResponse
from app.shared.security import (
    sanitize_name,
    sanitize_string_dict,
    sanitize_string_list,
    sanitize_text,
    validate_json_size,
)


class ProjectCreate(BaseModel):
    """Schema para criacao de um novo projeto."""

    name: str = Field(..., min_length=1, max_length=255, description='Nome do projeto')
    base_url: str = Field(..., max_length=500, description='URL base do site alvo')
    description: str | None = Field(None, description='Descricao do projeto')
    credentials: dict | None = Field(
        None,
        description='Credenciais de acesso ao site (ex: {username, password})',
    )
    llm_provider: str = Field(
        ...,
        min_length=1,
        max_length=50,
        description='Provedor LLM (anthropic, openai, google, ollama)',
    )
    llm_model: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description='Modelo LLM a ser utilizado',
    )
    llm_api_key: str | None = Field(None, description='Chave de API do provedor LLM')
    llm_temperature: float = Field(
        0.7,
        ge=0,
        le=2,
        description='Temperatura do LLM (0 a 2)',
    )
    llm_max_tokens: int = Field(
        4096,
        gt=0,
        description='Maximo de tokens de resposta do LLM',
    )
    llm_timeout: int = Field(
        120,
        gt=0,
        description='Timeout em segundos para chamadas ao LLM',
    )
    allowed_domains: list[str] | None = Field(
        None,
        description='Lista de dominios permitidos para navegacao do agente',
    )
    blocked_urls: list[str] | None = Field(
        None,
        description='Lista de padroes regex de URLs bloqueadas para o agente',
    )

    @field_validator('base_url')
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Valida que a URL base tem formato valido."""
        v = sanitize_text(v)
        parsed = urlparse(v)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(
                'URL invalida. Informe uma URL completa (ex: https://exemplo.com)'
            )
        if parsed.scheme not in ('http', 'https'):
            raise ValueError('URL deve usar protocolo http ou https')
        return v

    @field_validator('name')
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        """Valida que o nome nao esta vazio."""
        if not v or not v.strip():
            raise ValueError('O nome do projeto nao pode estar vazio')
        return sanitize_name(v)

    @field_validator('description')
    @classmethod
    def description_sanitized(cls, v: str | None) -> str | None:
        """Sanitiza descricao (se fornecida)."""
        if v is None:
            return v
        return sanitize_text(v)

    @field_validator('credentials')
    @classmethod
    def credentials_sanitized(cls, v: dict | None) -> dict | None:
        """Sanitiza credenciais (se fornecidas)."""
        sanitized = sanitize_string_dict(v) if v is not None else v
        return validate_json_size(sanitized, 50 * 1024, 'credentials')

    @field_validator('allowed_domains')
    @classmethod
    def allowed_domains_sanitized(cls, v: list[str] | None) -> list[str] | None:
        """Sanitiza lista de dominios permitidos."""
        return sanitize_string_list(v)

    @field_validator('blocked_urls')
    @classmethod
    def blocked_urls_sanitized(cls, v: list[str] | None) -> list[str] | None:
        """Sanitiza lista de URLs bloqueadas."""
        return sanitize_string_list(v)

    @field_validator('llm_provider')
    @classmethod
    def validate_llm_provider(cls, v: str) -> str:
        """Valida que o provedor LLM e suportado."""
        allowed_providers = ('anthropic', 'openai', 'openai-compatible', 'google', 'ollama', 'bedrock')
        if v.lower() not in allowed_providers:
            raise ValueError(
                f'Provedor LLM invalido. Valores permitidos: {", ".join(allowed_providers)}'
            )
        return v.lower()


class ProjectUpdate(BaseModel):
    """Schema para atualizacao de um projeto. Todos os campos sao opcionais."""

    name: str | None = Field(None, min_length=1, max_length=255)
    base_url: str | None = Field(None, max_length=500)
    description: str | None = Field(None)
    credentials: dict | None = Field(None)
    llm_provider: str | None = Field(None, min_length=1, max_length=50)
    llm_model: str | None = Field(None, min_length=1, max_length=100)
    llm_api_key: str | None = Field(None)
    llm_temperature: float | None = Field(None, ge=0, le=2)
    llm_max_tokens: int | None = Field(None, gt=0)
    llm_timeout: int | None = Field(None, gt=0)
    is_active: bool | None = Field(None)
    allowed_domains: list[str] | None = Field(
        None,
        description='Lista de dominios permitidos para navegacao do agente',
    )
    blocked_urls: list[str] | None = Field(
        None,
        description='Lista de padroes regex de URLs bloqueadas para o agente',
    )

    @field_validator('base_url')
    @classmethod
    def validate_base_url(cls, v: str | None) -> str | None:
        """Valida que a URL base tem formato valido (se fornecida)."""
        if v is None:
            return v
        v = sanitize_text(v)
        parsed = urlparse(v)
        if not parsed.scheme or not parsed.netloc:
            raise ValueError(
                'URL invalida. Informe uma URL completa (ex: https://exemplo.com)'
            )
        if parsed.scheme not in ('http', 'https'):
            raise ValueError('URL deve usar protocolo http ou https')
        return v

    @field_validator('name')
    @classmethod
    def name_not_empty(cls, v: str | None) -> str | None:
        """Valida que o nome nao esta vazio (se fornecido)."""
        if v is not None and not v.strip():
            raise ValueError('O nome do projeto nao pode estar vazio')
        return sanitize_name(v) if v is not None else v

    @field_validator('description')
    @classmethod
    def description_sanitized(cls, v: str | None) -> str | None:
        """Sanitiza descricao (se fornecida)."""
        if v is None:
            return v
        return sanitize_text(v)

    @field_validator('credentials')
    @classmethod
    def credentials_sanitized(cls, v: dict | None) -> dict | None:
        """Sanitiza credenciais (se fornecidas)."""
        sanitized = sanitize_string_dict(v) if v is not None else v
        return validate_json_size(sanitized, 50 * 1024, 'credentials')

    @field_validator('allowed_domains')
    @classmethod
    def allowed_domains_sanitized(cls, v: list[str] | None) -> list[str] | None:
        """Sanitiza lista de dominios permitidos."""
        return sanitize_string_list(v)

    @field_validator('blocked_urls')
    @classmethod
    def blocked_urls_sanitized(cls, v: list[str] | None) -> list[str] | None:
        """Sanitiza lista de URLs bloqueadas."""
        return sanitize_string_list(v)

    @field_validator('llm_provider')
    @classmethod
    def validate_llm_provider(cls, v: str | None) -> str | None:
        """Valida que o provedor LLM e suportado (se fornecido)."""
        if v is None:
            return v
        allowed_providers = ('anthropic', 'openai', 'openai-compatible', 'google', 'ollama', 'bedrock')
        if v.lower() not in allowed_providers:
            raise ValueError(
                f'Provedor LLM invalido. Valores permitidos: {", ".join(allowed_providers)}'
            )
        return v.lower()


class ProjectResponse(BaseModel):
    """
    Schema de resposta com dados do projeto.

    Nao expoe credenciais ou chave de API em texto puro.
    Em vez disso, indica se o projeto possui credenciais e/ou chave de API
    atraves dos campos has_credentials e has_llm_api_key.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    base_url: str
    description: str | None = None
    has_credentials: bool = False
    llm_provider: str
    llm_model: str
    has_llm_api_key: bool = False
    llm_temperature: float
    llm_max_tokens: int
    llm_timeout: int
    allowed_domains: list[str] | None = None
    blocked_urls: list[str] | None = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, project: 'Project') -> 'ProjectResponse':
        """
        Cria um ProjectResponse a partir de um modelo Project.

        Converte campos criptografados em indicadores booleanos.
        """
        return cls(
            id=project.id,
            name=project.name,
            base_url=project.base_url,
            description=project.description,
            has_credentials=project.encrypted_credentials is not None,
            llm_provider=project.llm_provider,
            llm_model=project.llm_model,
            has_llm_api_key=project.encrypted_llm_api_key is not None,
            llm_temperature=project.llm_temperature,
            llm_max_tokens=project.llm_max_tokens,
            llm_timeout=project.llm_timeout,
            allowed_domains=project.allowed_domains,
            blocked_urls=project.blocked_urls,
            is_active=project.is_active,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )


# Alias para resposta paginada de projetos
ProjectListResponse = PaginatedResponse[ProjectResponse]
