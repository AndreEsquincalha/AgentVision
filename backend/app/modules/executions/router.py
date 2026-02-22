import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, get_storage_client
from app.modules.auth.models import User
from app.modules.delivery.repository import DeliveryRepository
from app.modules.delivery.schemas import DeliveryLogResponse
from app.modules.delivery.service import DeliveryService
from app.modules.executions.repository import ExecutionRepository
from app.modules.executions.schemas import (
    ExecutionDetailResponse,
    ExecutionFilter,
    ExecutionListResponse,
    PdfUrlResponse,
    ScreenshotUrlResponse,
)
from app.modules.executions.service import ExecutionService
from app.shared.storage import StorageClient

router = APIRouter(
    prefix='/api/executions',
    tags=['Executions'],
)


# -------------------------------------------------------------------------
# Dependency injection chain: get_db -> repositories -> services
# -------------------------------------------------------------------------


def get_execution_repository(db: Session = Depends(get_db)) -> ExecutionRepository:
    """Dependency que fornece o repositorio de execucoes."""
    return ExecutionRepository(db)


def get_delivery_repository(db: Session = Depends(get_db)) -> DeliveryRepository:
    """Dependency que fornece o repositorio de entregas."""
    return DeliveryRepository(db)


def get_delivery_service(
    repository: DeliveryRepository = Depends(get_delivery_repository),
) -> DeliveryService:
    """Dependency que fornece o servico de entregas."""
    return DeliveryService(repository)


def get_execution_service(
    execution_repository: ExecutionRepository = Depends(get_execution_repository),
    storage_client: StorageClient = Depends(get_storage_client),
    delivery_service: DeliveryService = Depends(get_delivery_service),
) -> ExecutionService:
    """Dependency que fornece o servico de execucoes."""
    return ExecutionService(execution_repository, storage_client, delivery_service)


# -------------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------------


@router.get('', response_model=ExecutionListResponse)
def list_executions(
    page: int = Query(1, ge=1, description='Numero da pagina'),
    per_page: int = Query(20, ge=1, le=100, description='Itens por pagina'),
    job_id: uuid.UUID | None = Query(None, description='Filtrar por job'),
    project_id: uuid.UUID | None = Query(None, description='Filtrar por projeto'),
    status: str | None = Query(None, description='Filtrar por status'),
    date_from: datetime | None = Query(None, description='Data/hora inicial'),
    date_to: datetime | None = Query(None, description='Data/hora final'),
    is_dry_run: bool | None = Query(None, description='Filtrar por dry run'),
    current_user: User = Depends(get_current_user),
    service: ExecutionService = Depends(get_execution_service),
) -> ExecutionListResponse:
    """
    Lista todas as execucoes com paginacao e filtros.

    Suporta filtros por job, projeto, status, periodo e dry run.
    Retorna campos reduzidos para listagem.
    """
    filters = ExecutionFilter(
        job_id=job_id,
        project_id=project_id,
        status=status,
        date_from=date_from,
        date_to=date_to,
        is_dry_run=is_dry_run,
    )

    return service.list_executions(
        page=page,
        per_page=per_page,
        filters=filters,
    )


@router.get('/{execution_id}', response_model=ExecutionDetailResponse)
def get_execution(
    execution_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: ExecutionService = Depends(get_execution_service),
) -> ExecutionDetailResponse:
    """
    Retorna os dados completos de uma execucao.

    Inclui logs de execucao, dados extraidos, e logs de entrega associados.
    """
    return service.get_execution(execution_id)


@router.get('/{execution_id}/screenshots', response_model=ScreenshotUrlResponse)
def get_screenshots(
    execution_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: ExecutionService = Depends(get_execution_service),
) -> ScreenshotUrlResponse:
    """
    Retorna URLs presigned para os screenshots de uma execucao.

    As URLs sao temporarias (validas por 1 hora) e permitem acesso
    direto aos arquivos de imagem armazenados no MinIO.
    """
    return service.get_screenshot_urls(execution_id)


@router.get('/{execution_id}/pdf', response_model=PdfUrlResponse)
def get_pdf(
    execution_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: ExecutionService = Depends(get_execution_service),
) -> PdfUrlResponse:
    """
    Retorna URL presigned para o PDF de uma execucao.

    A URL e temporaria (valida por 1 hora) e permite acesso direto
    ao arquivo PDF armazenado no MinIO.
    """
    return service.get_pdf_url(execution_id)


@router.post(
    '/{execution_id}/retry-delivery/{delivery_log_id}',
    response_model=DeliveryLogResponse,
)
def retry_delivery(
    execution_id: uuid.UUID,
    delivery_log_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: ExecutionService = Depends(get_execution_service),
) -> DeliveryLogResponse:
    """
    Retenta uma entrega que falhou para uma execucao.

    Somente entregas com status 'failed' podem ser retentadas.
    Utiliza as mesmas configuracoes de canal da entrega original.
    """
    return service.retry_delivery(execution_id, delivery_log_id)
