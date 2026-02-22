import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.delivery.repository import DeliveryRepository
from app.modules.delivery.schemas import (
    DeliveryConfigCreate,
    DeliveryConfigResponse,
    DeliveryConfigUpdate,
    DeliveryLogResponse,
)
from app.modules.delivery.service import DeliveryService
from app.shared.schemas import MessageResponse

router = APIRouter(
    prefix='/api/delivery',
    tags=['Delivery'],
)


# -------------------------------------------------------------------------
# Dependency injection chain: get_db -> repository -> service
# -------------------------------------------------------------------------


def get_delivery_repository(db: Session = Depends(get_db)) -> DeliveryRepository:
    """Dependency que fornece o repositorio de entregas."""
    return DeliveryRepository(db)


def get_delivery_service(
    repository: DeliveryRepository = Depends(get_delivery_repository),
) -> DeliveryService:
    """Dependency que fornece o servico de entregas."""
    return DeliveryService(repository)


# -------------------------------------------------------------------------
# Endpoints - Configuracoes de entrega
# -------------------------------------------------------------------------


@router.get('/configs', response_model=list[DeliveryConfigResponse])
def list_delivery_configs(
    job_id: uuid.UUID = Query(..., description='ID do job'),
    current_user: User = Depends(get_current_user),
    service: DeliveryService = Depends(get_delivery_service),
) -> list[DeliveryConfigResponse]:
    """
    Lista todas as configuracoes de entrega de um job.

    Retorna as configuracoes ativas e inativas (nao excluidas) do job.
    """
    return service.get_configs_by_job(job_id)


@router.get('/configs/{config_id}', response_model=DeliveryConfigResponse)
def get_delivery_config(
    config_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: DeliveryService = Depends(get_delivery_service),
) -> DeliveryConfigResponse:
    """
    Retorna os dados de uma configuracao de entrega especifica.
    """
    return service.get_config(config_id)


@router.post('/configs', response_model=DeliveryConfigResponse, status_code=201)
def create_delivery_config(
    data: DeliveryConfigCreate,
    current_user: User = Depends(get_current_user),
    service: DeliveryService = Depends(get_delivery_service),
) -> DeliveryConfigResponse:
    """
    Cria uma nova configuracao de entrega para um job.

    A configuracao define como os resultados serao entregues
    (email, webhook, etc.) e para quem.
    """
    return service.create_config(data)


@router.put('/configs/{config_id}', response_model=DeliveryConfigResponse)
def update_delivery_config(
    config_id: uuid.UUID,
    data: DeliveryConfigUpdate,
    current_user: User = Depends(get_current_user),
    service: DeliveryService = Depends(get_delivery_service),
) -> DeliveryConfigResponse:
    """
    Atualiza uma configuracao de entrega existente.

    Apenas os campos fornecidos serao atualizados.
    """
    return service.update_config(config_id, data)


@router.delete('/configs/{config_id}', response_model=MessageResponse)
def delete_delivery_config(
    config_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: DeliveryService = Depends(get_delivery_service),
) -> MessageResponse:
    """
    Realiza soft delete de uma configuracao de entrega.
    """
    service.delete_config(config_id)
    return MessageResponse(
        success=True,
        message='Configuracao de entrega excluida com sucesso',
    )


# -------------------------------------------------------------------------
# Endpoints - Logs de entrega
# -------------------------------------------------------------------------


@router.get('/logs', response_model=list[DeliveryLogResponse])
def list_delivery_logs(
    execution_id: uuid.UUID = Query(..., description='ID da execucao'),
    current_user: User = Depends(get_current_user),
    service: DeliveryService = Depends(get_delivery_service),
) -> list[DeliveryLogResponse]:
    """
    Lista logs de entrega de uma execucao.

    Retorna o historico de tentativas de entrega para uma execucao especifica.
    """
    return service.get_logs_by_execution(execution_id)


@router.post('/logs/{log_id}/retry', response_model=DeliveryLogResponse)
def retry_delivery(
    log_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    service: DeliveryService = Depends(get_delivery_service),
) -> DeliveryLogResponse:
    """
    Retenta uma entrega que falhou.

    Somente entregas com status 'failed' podem ser retentadas.
    """
    return service.retry_delivery(log_id)
