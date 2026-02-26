import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.modules.auth.models import User
from app.modules.prompts.repository import PromptTemplateRepository
from app.modules.prompts.schemas import (
    PromptTemplateCreate,
    PromptTemplateListResponse,
    PromptTemplateResponse,
    PromptTemplateUpdate,
)
from app.modules.prompts.service import PromptTemplateService
from app.shared.schemas import MessageResponse

router = APIRouter(
    prefix='/api/prompts',
    tags=['Prompts'],
)


# -------------------------------------------------------------------------
# Dependency injection chain: get_db -> repository -> service
# -------------------------------------------------------------------------


def get_prompt_template_repository(
    db: Session = Depends(get_db),
) -> PromptTemplateRepository:
    """Dependency que fornece o repositorio de templates de prompt."""
    return PromptTemplateRepository(db)


def get_prompt_template_service(
    repository: PromptTemplateRepository = Depends(get_prompt_template_repository),
) -> PromptTemplateService:
    """Dependency que fornece o servico de templates de prompt."""
    return PromptTemplateService(repository)


# -------------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------------


@router.get('', response_model=PromptTemplateListResponse)
def list_templates(
    page: int = Query(1, ge=1, description='Numero da pagina'),
    per_page: int = Query(20, ge=1, le=100, description='Itens por pagina'),
    search: str | None = Query(None, description='Busca por nome ou descricao'),
    category: str | None = Query(None, description='Filtrar por categoria'),
    current_user: User = Depends(require_roles('admin', 'operator')),
    service: PromptTemplateService = Depends(get_prompt_template_service),
) -> PromptTemplateListResponse:
    """
    Lista todos os templates de prompt com paginacao e filtros.

    Retorna uma lista paginada de templates, com opcao de filtrar
    por nome/descricao e categoria.
    """
    return service.list_templates(
        page=page,
        per_page=per_page,
        search=search,
        category=category,
    )


@router.get('/{template_id}', response_model=PromptTemplateResponse)
def get_template(
    template_id: uuid.UUID,
    current_user: User = Depends(require_roles('admin', 'operator')),
    service: PromptTemplateService = Depends(get_prompt_template_service),
) -> PromptTemplateResponse:
    """Retorna os dados de um template de prompt especifico."""
    return service.get_template(template_id)


@router.post('', response_model=PromptTemplateResponse, status_code=201)
def create_template(
    data: PromptTemplateCreate,
    current_user: User = Depends(require_roles('admin', 'operator')),
    service: PromptTemplateService = Depends(get_prompt_template_service),
) -> PromptTemplateResponse:
    """
    Cria um novo template de prompt.

    O template e criado com version=1.
    """
    return service.create_template(data)


@router.put('/{template_id}', response_model=PromptTemplateResponse)
def update_template(
    template_id: uuid.UUID,
    data: PromptTemplateUpdate,
    current_user: User = Depends(require_roles('admin', 'operator')),
    service: PromptTemplateService = Depends(get_prompt_template_service),
) -> PromptTemplateResponse:
    """
    Atualiza um template de prompt existente.

    Apenas os campos fornecidos serao atualizados. A cada atualizacao,
    o campo version e incrementado automaticamente.
    """
    return service.update_template(template_id, data)


@router.delete('/{template_id}', response_model=MessageResponse)
def delete_template(
    template_id: uuid.UUID,
    current_user: User = Depends(require_roles('admin', 'operator')),
    service: PromptTemplateService = Depends(get_prompt_template_service),
) -> MessageResponse:
    """
    Realiza soft delete de um template de prompt.

    O template nao e removido do banco de dados, apenas marcado como excluido.
    """
    service.delete_template(template_id)
    return MessageResponse(
        success=True,
        message='Template de prompt excluido com sucesso',
    )
