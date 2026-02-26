import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.modules.auth.models import User
from app.modules.delivery.repository import DeliveryRepository
from app.modules.jobs.repository import JobRepository
from app.modules.jobs.schemas import (
    DryRunResponse,
    JobCreate,
    JobListResponse,
    JobResponse,
    JobToggle,
    JobUpdate,
)
from app.modules.jobs.service import JobService
from app.modules.projects.repository import ProjectRepository
from app.shared.schemas import MessageResponse

router = APIRouter(
    prefix='/api/jobs',
    tags=['Jobs'],
)


# -------------------------------------------------------------------------
# Dependency injection chain: get_db -> repositories -> service
# -------------------------------------------------------------------------


def get_job_repository(db: Session = Depends(get_db)) -> JobRepository:
    """Dependency que fornece o repositorio de jobs."""
    return JobRepository(db)


def get_project_repository(db: Session = Depends(get_db)) -> ProjectRepository:
    """Dependency que fornece o repositorio de projetos."""
    return ProjectRepository(db)


def get_delivery_repository(db: Session = Depends(get_db)) -> DeliveryRepository:
    """Dependency que fornece o repositorio de entregas."""
    return DeliveryRepository(db)


def get_job_service(
    job_repository: JobRepository = Depends(get_job_repository),
    project_repository: ProjectRepository = Depends(get_project_repository),
    delivery_repository: DeliveryRepository = Depends(get_delivery_repository),
) -> JobService:
    """Dependency que fornece o servico de jobs."""
    return JobService(job_repository, project_repository, delivery_repository)


# -------------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------------


@router.get('', response_model=JobListResponse)
def list_jobs(
    page: int = Query(1, ge=1, description='Numero da pagina'),
    per_page: int = Query(20, ge=1, le=100, description='Itens por pagina'),
    project_id: uuid.UUID | None = Query(None, description='Filtrar por projeto'),
    is_active: bool | None = Query(None, description='Filtrar por status ativo/inativo'),
    search: str | None = Query(None, description='Busca por nome'),
    current_user: User = Depends(require_roles('admin', 'operator')),
    service: JobService = Depends(get_job_service),
) -> JobListResponse:
    """
    Lista todos os jobs com paginacao e filtros.

    Suporta filtros por projeto, status ativo e busca por nome.
    Inclui o nome do projeto associado e proxima execucao calculada.
    """
    return service.list_jobs(
        page=page,
        per_page=per_page,
        project_id=project_id,
        is_active=is_active,
        search=search,
    )


@router.get('/{job_id}', response_model=JobResponse)
def get_job(
    job_id: uuid.UUID,
    current_user: User = Depends(require_roles('admin', 'operator')),
    service: JobService = Depends(get_job_service),
) -> JobResponse:
    """
    Retorna os dados de um job especifico.

    Inclui o nome do projeto, configuracoes de entrega e proxima execucao.
    """
    return service.get_job(job_id)


@router.post('', response_model=JobResponse, status_code=201)
def create_job(
    data: JobCreate,
    current_user: User = Depends(require_roles('admin', 'operator')),
    service: JobService = Depends(get_job_service),
) -> JobResponse:
    """
    Cria um novo job.

    Valida que o projeto existe e esta ativo. Opcionalmente cria
    configuracoes de entrega associadas na mesma transacao.
    """
    return service.create_job(data)


@router.put('/{job_id}', response_model=JobResponse)
def update_job(
    job_id: uuid.UUID,
    data: JobUpdate,
    current_user: User = Depends(require_roles('admin', 'operator')),
    service: JobService = Depends(get_job_service),
) -> JobResponse:
    """
    Atualiza um job existente.

    Apenas os campos fornecidos serao atualizados.
    """
    return service.update_job(job_id, data)


@router.delete('/{job_id}', response_model=MessageResponse)
def delete_job(
    job_id: uuid.UUID,
    current_user: User = Depends(require_roles('admin', 'operator')),
    service: JobService = Depends(get_job_service),
) -> MessageResponse:
    """
    Realiza soft delete de um job.

    O job nao e removido do banco de dados, apenas marcado como excluido.
    """
    service.delete_job(job_id)
    return MessageResponse(
        success=True,
        message='Job excluido com sucesso',
    )


@router.patch('/{job_id}/toggle', response_model=JobResponse)
def toggle_job(
    job_id: uuid.UUID,
    data: JobToggle,
    current_user: User = Depends(require_roles('admin', 'operator')),
    service: JobService = Depends(get_job_service),
) -> JobResponse:
    """
    Ativa ou desativa um job.

    Alterna o status is_active do job.
    """
    return service.toggle_active(job_id, data)


@router.post('/{job_id}/dry-run', response_model=DryRunResponse, status_code=202)
def trigger_dry_run(
    job_id: uuid.UUID,
    current_user: User = Depends(require_roles('admin', 'operator')),
    service: JobService = Depends(get_job_service),
) -> DryRunResponse:
    """
    Inicia um dry run para um job.

    Cria uma execucao de teste (dry run) que sera processada pelo worker.
    O dry run nao envia entregas reais.
    """
    return service.trigger_dry_run(job_id)
