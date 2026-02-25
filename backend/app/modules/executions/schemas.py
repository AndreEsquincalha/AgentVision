import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.modules.delivery.schemas import DeliveryLogResponse
from app.shared.schemas import PaginatedResponse


class ExecutionFilter(BaseModel):
    """Schema de filtros para listagem de execucoes."""

    job_id: uuid.UUID | None = Field(
        None,
        description='Filtrar por job',
    )
    project_id: uuid.UUID | None = Field(
        None,
        description='Filtrar por projeto',
    )
    status: str | None = Field(
        None,
        description='Filtrar por status (pending, running, success, failed, cancelled)',
    )
    date_from: datetime | None = Field(
        None,
        description='Data/hora inicial para filtro de periodo',
    )
    date_to: datetime | None = Field(
        None,
        description='Data/hora final para filtro de periodo',
    )
    is_dry_run: bool | None = Field(
        None,
        description='Filtrar por dry run (true/false)',
    )


class ExecutionResponse(BaseModel):
    """
    Schema de resposta com dados da execucao.

    Inclui os nomes do job e do projeto associados.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    job_name: str | None = None
    project_name: str | None = None
    status: str
    celery_task_id: str | None = None
    logs: str | None = None
    extracted_data: dict | None = None
    screenshots_path: str | None = None
    pdf_path: str | None = None
    is_dry_run: bool
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: int | None = None
    last_heartbeat: datetime | None = None
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, execution: 'Execution') -> 'ExecutionResponse':
        """
        Cria um ExecutionResponse a partir de um modelo Execution.

        Inclui nomes do job e do projeto associados via relacionamentos.
        """
        job_name: str | None = None
        project_name: str | None = None

        if hasattr(execution, 'job') and execution.job:
            job_name = execution.job.name
            if hasattr(execution.job, 'project') and execution.job.project:
                project_name = execution.job.project.name

        # Acessa campos novos com seguranca (podem nao existir em migracoes pendentes)
        celery_task_id: str | None = getattr(execution, 'celery_task_id', None)
        last_heartbeat: datetime | None = getattr(execution, 'last_heartbeat', None)

        return cls(
            id=execution.id,
            job_id=execution.job_id,
            job_name=job_name,
            project_name=project_name,
            status=execution.status,
            celery_task_id=celery_task_id,
            logs=execution.logs,
            extracted_data=execution.extracted_data,
            screenshots_path=execution.screenshots_path,
            pdf_path=execution.pdf_path,
            is_dry_run=execution.is_dry_run,
            started_at=execution.started_at,
            finished_at=execution.finished_at,
            duration_seconds=execution.duration_seconds,
            last_heartbeat=last_heartbeat,
            created_at=execution.created_at,
            updated_at=execution.updated_at,
        )


class ExecutionListItemResponse(BaseModel):
    """
    Schema de resposta reduzida para listagem de execucoes.

    Contem apenas os campos essenciais para exibicao em listas.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    job_name: str | None = None
    project_name: str | None = None
    status: str
    is_dry_run: bool
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: int | None = None
    created_at: datetime

    @classmethod
    def from_model(cls, execution: 'Execution') -> 'ExecutionListItemResponse':
        """
        Cria um ExecutionListItemResponse a partir de um modelo Execution.

        Versao reduzida para uso em listas paginadas.
        """
        job_name: str | None = None
        project_name: str | None = None

        if hasattr(execution, 'job') and execution.job:
            job_name = execution.job.name
            if hasattr(execution.job, 'project') and execution.job.project:
                project_name = execution.job.project.name

        return cls(
            id=execution.id,
            job_id=execution.job_id,
            job_name=job_name,
            project_name=project_name,
            status=execution.status,
            is_dry_run=execution.is_dry_run,
            started_at=execution.started_at,
            finished_at=execution.finished_at,
            duration_seconds=execution.duration_seconds,
            created_at=execution.created_at,
        )


class ExecutionDetailResponse(BaseModel):
    """
    Schema de resposta completa para detalhes de uma execucao.

    Inclui todos os campos da execucao, nomes do job e projeto,
    e a lista de logs de entrega associados.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_id: uuid.UUID
    job_name: str | None = None
    project_name: str | None = None
    status: str
    celery_task_id: str | None = None
    logs: str | None = None
    extracted_data: dict | None = None
    screenshots_path: str | None = None
    pdf_path: str | None = None
    is_dry_run: bool
    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_seconds: int | None = None
    last_heartbeat: datetime | None = None
    delivery_logs: list[DeliveryLogResponse] = []
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, execution: 'Execution') -> 'ExecutionDetailResponse':
        """
        Cria um ExecutionDetailResponse a partir de um modelo Execution.

        Inclui nomes do job e projeto, e logs de entrega completos.
        """
        job_name: str | None = None
        project_name: str | None = None

        if hasattr(execution, 'job') and execution.job:
            job_name = execution.job.name
            if hasattr(execution.job, 'project') and execution.job.project:
                project_name = execution.job.project.name

        # Converte delivery_logs do modelo para schemas de resposta
        delivery_log_responses: list[DeliveryLogResponse] = []
        if hasattr(execution, 'delivery_logs') and execution.delivery_logs:
            delivery_log_responses = [
                DeliveryLogResponse.model_validate(dl)
                for dl in execution.delivery_logs
            ]

        # Acessa campos novos com seguranca (podem nao existir em migracoes pendentes)
        celery_task_id: str | None = getattr(execution, 'celery_task_id', None)
        last_heartbeat: datetime | None = getattr(execution, 'last_heartbeat', None)

        return cls(
            id=execution.id,
            job_id=execution.job_id,
            job_name=job_name,
            project_name=project_name,
            status=execution.status,
            celery_task_id=celery_task_id,
            logs=execution.logs,
            extracted_data=execution.extracted_data,
            screenshots_path=execution.screenshots_path,
            pdf_path=execution.pdf_path,
            is_dry_run=execution.is_dry_run,
            started_at=execution.started_at,
            finished_at=execution.finished_at,
            duration_seconds=execution.duration_seconds,
            last_heartbeat=last_heartbeat,
            delivery_logs=delivery_log_responses,
            created_at=execution.created_at,
            updated_at=execution.updated_at,
        )


class ScreenshotUrlResponse(BaseModel):
    """Schema de resposta com URLs presigned de screenshots."""

    model_config = ConfigDict(from_attributes=True)

    execution_id: uuid.UUID
    urls: list[str]


class PdfUrlResponse(BaseModel):
    """Schema de resposta com URL presigned do PDF."""

    model_config = ConfigDict(from_attributes=True)

    execution_id: uuid.UUID
    url: str


# Alias para resposta paginada de execucoes
ExecutionListResponse = PaginatedResponse[ExecutionListItemResponse]
