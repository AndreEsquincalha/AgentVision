import uuid
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict

T = TypeVar('T')


class BaseSchema(BaseModel):
    """Schema base com campos padrao de resposta."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class SoftDeleteSchema(BaseSchema):
    """Schema base com campo de soft delete."""

    deleted_at: datetime | None = None


class PaginationParams(BaseModel):
    """Parametros de paginacao para requisicoes."""

    page: int = 1
    per_page: int = 20

    @property
    def offset(self) -> int:
        """Calcula o offset com base na pagina e itens por pagina."""
        return (self.page - 1) * self.per_page


class PaginatedResponse(BaseModel, Generic[T]):
    """Resposta paginada generica."""

    model_config = ConfigDict(from_attributes=True)

    items: list[T]
    total: int
    page: int
    per_page: int
    total_pages: int

    @classmethod
    def create(
        cls,
        items: list[T],
        total: int,
        page: int,
        per_page: int,
    ) -> 'PaginatedResponse[T]':
        """Cria uma resposta paginada calculando o total de paginas."""
        total_pages = (total + per_page - 1) // per_page if per_page > 0 else 0
        return cls(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
            total_pages=total_pages,
        )


class MessageResponse(BaseModel):
    """Resposta padrao com mensagem de sucesso/erro."""

    success: bool
    message: str
    data: Any | None = None
