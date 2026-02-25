import json
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


class StructuredLogEntry(BaseModel):
    """Schema de resposta para uma entrada de log estruturado."""

    model_config = ConfigDict(from_attributes=True)

    timestamp: str
    level: str
    phase: str
    message: str
    metadata: dict | None = None


def _parse_structured_logs(logs: str | None) -> list[StructuredLogEntry] | None:
    """
    Tenta parsear logs como JSON estruturado.

    Se o conteudo for JSON valido (lista de objetos), retorna as entradas
    parseadas. Se for texto simples (formato legado), retorna None.

    Args:
        logs: String de logs (JSON ou texto).

    Returns:
        Lista de entradas estruturadas ou None se formato legado.
    """
    if not logs:
        return None
    try:
        data = json.loads(logs)
        if isinstance(data, list) and len(data) > 0:
            return [
                StructuredLogEntry(
                    timestamp=item.get('timestamp', ''),
                    level=item.get('level', 'INFO'),
                    phase=item.get('phase', 'unknown'),
                    message=item.get('message', ''),
                    metadata=item.get('metadata'),
                )
                for item in data
                if isinstance(item, dict)
            ]
    except (json.JSONDecodeError, TypeError):
        pass
    return None


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
    progress_percent: int = 0
    celery_task_id: str | None = None
    logs: str | None = None
    structured_logs: list[StructuredLogEntry] | None = None
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
        progress_percent: int = getattr(execution, 'progress_percent', 0) or 0

        # Parseia logs estruturados se disponivel
        raw_logs: str | None = execution.logs
        structured = _parse_structured_logs(raw_logs)

        return cls(
            id=execution.id,
            job_id=execution.job_id,
            job_name=job_name,
            project_name=project_name,
            status=execution.status,
            progress_percent=progress_percent,
            celery_task_id=celery_task_id,
            logs=raw_logs,
            structured_logs=structured,
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
    progress_percent: int = 0
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

        progress_percent: int = getattr(execution, 'progress_percent', 0) or 0

        return cls(
            id=execution.id,
            job_id=execution.job_id,
            job_name=job_name,
            project_name=project_name,
            status=execution.status,
            progress_percent=progress_percent,
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
    progress_percent: int = 0
    celery_task_id: str | None = None
    logs: str | None = None
    structured_logs: list[StructuredLogEntry] | None = None
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
        progress_percent: int = getattr(execution, 'progress_percent', 0) or 0

        # Parseia logs estruturados se disponivel
        raw_logs: str | None = execution.logs
        structured = _parse_structured_logs(raw_logs)

        return cls(
            id=execution.id,
            job_id=execution.job_id,
            job_name=job_name,
            project_name=project_name,
            status=execution.status,
            progress_percent=progress_percent,
            celery_task_id=celery_task_id,
            logs=raw_logs,
            structured_logs=structured,
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
