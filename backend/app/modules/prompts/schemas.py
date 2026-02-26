import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.shared.schemas import PaginatedResponse
from app.shared.security import sanitize_name, sanitize_text


class PromptTemplateCreate(BaseModel):
    """Schema para criacao de um novo template de prompt."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description='Nome do template',
    )
    content: str = Field(
        ...,
        min_length=1,
        description='Conteudo do template de prompt',
    )
    description: str | None = Field(
        None,
        description='Descricao do template',
    )
    category: str | None = Field(
        None,
        max_length=100,
        description='Categoria do template (ex: extraction, analysis)',
    )

    @field_validator('name')
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        """Valida que o nome nao esta vazio."""
        if not v or not v.strip():
            raise ValueError('O nome do template nao pode estar vazio')
        return sanitize_name(v)

    @field_validator('content')
    @classmethod
    def content_not_empty(cls, v: str) -> str:
        """Valida que o conteudo nao esta vazio."""
        if not v or not v.strip():
            raise ValueError('O conteudo do template nao pode estar vazio')
        return sanitize_text(v)

    @field_validator('description')
    @classmethod
    def description_sanitized(cls, v: str | None) -> str | None:
        """Sanitiza descricao (se fornecida)."""
        if v is None:
            return v
        return sanitize_text(v)

    @field_validator('category')
    @classmethod
    def category_sanitized(cls, v: str | None) -> str | None:
        """Sanitiza categoria (se fornecida)."""
        if v is None:
            return v
        return sanitize_text(v)


class PromptTemplateUpdate(BaseModel):
    """
    Schema para atualizacao de um template de prompt.

    Todos os campos sao opcionais. A cada atualizacao, o campo version
    e incrementado automaticamente pelo servico.
    """

    content: str | None = Field(
        None,
        description='Novo conteudo do template',
    )
    description: str | None = Field(
        None,
        description='Nova descricao do template',
    )
    category: str | None = Field(
        None,
        max_length=100,
        description='Nova categoria do template',
    )

    @field_validator('content')
    @classmethod
    def content_not_empty(cls, v: str | None) -> str | None:
        """Valida que o conteudo nao esta vazio (se fornecido)."""
        if v is not None and not v.strip():
            raise ValueError('O conteudo do template nao pode estar vazio')
        return sanitize_text(v) if v is not None else v

    @field_validator('description')
    @classmethod
    def description_sanitized(cls, v: str | None) -> str | None:
        """Sanitiza descricao (se fornecida)."""
        if v is None:
            return v
        return sanitize_text(v)

    @field_validator('category')
    @classmethod
    def category_sanitized(cls, v: str | None) -> str | None:
        """Sanitiza categoria (se fornecida)."""
        if v is None:
            return v
        return sanitize_text(v)


class PromptTemplateResponse(BaseModel):
    """Schema de resposta com dados do template de prompt."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    content: str
    description: str | None = None
    category: str | None = None
    version: int
    created_at: datetime
    updated_at: datetime


# Alias para resposta paginada de templates
PromptTemplateListResponse = PaginatedResponse[PromptTemplateResponse]
