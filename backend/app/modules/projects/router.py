import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.projects.repository import ProjectRepository
from app.modules.projects.schemas import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)
from app.modules.projects.service import ProjectService
from app.shared.schemas import MessageResponse

router = APIRouter(
    prefix='/api/projects',
    tags=['Projects'],
)


# -------------------------------------------------------------------------
# Dependency injection chain: get_db -> repository -> service
# -------------------------------------------------------------------------


def get_project_repository(db: Session = Depends(get_db)) -> ProjectRepository:
    """Dependency que fornece o repositorio de projetos."""
    return ProjectRepository(db)


def get_project_service(
    repository: ProjectRepository = Depends(get_project_repository),
) -> ProjectService:
    """Dependency que fornece o servico de projetos."""
    return ProjectService(repository)


# -------------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------------


@router.get('', response_model=ProjectListResponse)
def list_projects(
    page: int = Query(1, ge=1, description='Numero da pagina'),
    per_page: int = Query(20, ge=1, le=100, description='Itens por pagina'),
    search: str | None = Query(None, description='Busca por nome ou descricao'),
    is_active: bool | None = Query(None, description='Filtrar por status ativo/inativo'),
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
) -> ProjectListResponse:
    """
    Lista todos os projetos com paginacao e filtros.

    Retorna uma lista paginada de projetos, com opcao de filtrar
    por nome/descricao e status ativo.
    """
    return service.list_projects(
        page=page,
        per_page=per_page,
        search=search,
        is_active=is_active,
    )


@router.get('/{project_id}', response_model=ProjectResponse)
def get_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    """
    Retorna os dados de um projeto especifico.

    Nao expoe credenciais ou chave de API em texto puro.
    """
    return service.get_project(project_id)


@router.post('', response_model=ProjectResponse, status_code=201)
def create_project(
    data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    """
    Cria um novo projeto.

    Credenciais e chave de API do LLM sao criptografadas antes de serem salvas.
    """
    return service.create_project(data)


@router.put('/{project_id}', response_model=ProjectResponse)
def update_project(
    project_id: uuid.UUID,
    data: ProjectUpdate,
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
) -> ProjectResponse:
    """
    Atualiza um projeto existente.

    Apenas os campos fornecidos serao atualizados. Credenciais e chave de API
    sao recriptografadas quando fornecidas.
    """
    return service.update_project(project_id, data)


@router.delete('/{project_id}', response_model=MessageResponse)
def delete_project(
    project_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: ProjectService = Depends(get_project_service),
) -> MessageResponse:
    """
    Realiza soft delete de um projeto.

    O projeto nao e removido do banco de dados, apenas marcado como excluido.
    """
    service.delete_project(project_id)
    return MessageResponse(
        success=True,
        message='Projeto excluido com sucesso',
    )
