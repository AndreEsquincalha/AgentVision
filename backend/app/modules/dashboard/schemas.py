import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ExecutionStatusCounts(BaseModel):
    """Contagens de execucoes por status."""

    model_config = ConfigDict(from_attributes=True)

    pending: int = 0
    running: int = 0
    success: int = 0
    failed: int = 0


class DashboardSummaryResponse(BaseModel):
    """
    Schema de resposta do resumo do dashboard.

    Inclui contagens de projetos, jobs e execucoes do dia,
    alem da taxa de sucesso dos ultimos 7 dias.
    """

    model_config = ConfigDict(from_attributes=True)

    active_projects: int
    active_jobs: int
    inactive_jobs: int
    executions_today: ExecutionStatusCounts
    success_rate: float


class RecentExecutionResponse(BaseModel):
    """
    Schema de resposta para execucoes recentes.

    Representa uma execucao com informacoes do job e projeto associados.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_name: str
    project_name: str
    status: str
    started_at: datetime
    duration_seconds: int | None = None


class UpcomingExecutionResponse(BaseModel):
    """
    Schema de resposta para proximas execucoes agendadas.

    Representa um job ativo com a data do proximo disparo calculada a partir do cron.
    """

    model_config = ConfigDict(from_attributes=True)

    job_id: uuid.UUID
    job_name: str
    project_name: str
    next_run: datetime


class RecentFailureResponse(BaseModel):
    """
    Schema de resposta para falhas recentes.

    Representa uma execucao com falha das ultimas 24 horas.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    job_name: str
    project_name: str
    started_at: datetime
    error_summary: str
