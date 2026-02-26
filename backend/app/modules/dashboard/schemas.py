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

    # Campos extras para o frontend
    today_executions: int = 0
    today_success: int = 0
    today_failed: int = 0
    today_running: int = 0
    success_rate_7d: float = 0.0


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


class ProviderUsageResponse(BaseModel):
    """Consumo de tokens por provider."""

    model_config = ConfigDict(from_attributes=True)

    provider: str
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    total_images: int = 0
    estimated_cost_usd: float = 0.0
    call_count: int = 0


class TokenUsageResponse(BaseModel):
    """
    Schema de resposta agregada de consumo de tokens.

    Inclui total de tokens, custo estimado, consumo por provider
    e media por execucao.
    """

    model_config = ConfigDict(from_attributes=True)

    total_tokens: int = 0
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    estimated_cost_usd: float = 0.0
    total_images: int = 0
    total_calls: int = 0
    avg_tokens_per_call: float = 0.0
    usage_by_provider: list[ProviderUsageResponse] = []


class ExecutionsPerHourResponse(BaseModel):
    """Execucoes agrupadas por hora (ultimas 24h)."""

    model_config = ConfigDict(from_attributes=True)

    hour: str  # ISO format: "2026-02-26T14:00:00"
    total: int = 0
    success: int = 0
    failed: int = 0


class DurationByJobResponse(BaseModel):
    """Duracao media de execucao por job (top 10)."""

    model_config = ConfigDict(from_attributes=True)

    job_id: uuid.UUID
    job_name: str
    avg_duration_seconds: float
    execution_count: int


class CeleryWorkerStatusResponse(BaseModel):
    """Status de um worker Celery."""

    model_config = ConfigDict(from_attributes=True)

    name: str
    status: str  # online, offline
    active_tasks: int = 0


class OperationalMetricsResponse(BaseModel):
    """Metricas operacionais agregadas para o dashboard."""

    model_config = ConfigDict(from_attributes=True)

    executions_per_hour: list[ExecutionsPerHourResponse] = []
    duration_by_job: list[DurationByJobResponse] = []
    workers: list[CeleryWorkerStatusResponse] = []
    total_tokens_today: int = 0
    avg_duration_today: float = 0.0


class LLMProviderHealthResponse(BaseModel):
    """Status de saude de um provider LLM."""

    model_config = ConfigDict(from_attributes=True)

    provider: str
    status: str  # online, degraded, offline, unknown
    latency_ms: float = 0.0
    last_check: float = 0.0
    error: str | None = None


class LLMProviderHealthListResponse(BaseModel):
    """Lista de status de saude dos providers LLM."""

    model_config = ConfigDict(from_attributes=True)

    providers: list[LLMProviderHealthResponse] = []
    circuit_breakers: dict[str, str] = {}  # provider -> state
