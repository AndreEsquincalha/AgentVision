from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.dashboard.schemas import (
    DashboardSummaryResponse,
    RecentExecutionResponse,
    RecentFailureResponse,
    TokenUsageResponse,
    UpcomingExecutionResponse,
)
from app.modules.dashboard.service import DashboardService

router = APIRouter(
    prefix='/api/dashboard',
    tags=['Dashboard'],
)


def get_dashboard_service(db: Session = Depends(get_db)) -> DashboardService:
    """Dependency que fornece o servico do dashboard."""
    return DashboardService(db)


@router.get('/summary', response_model=DashboardSummaryResponse)
def get_summary(
    current_user: User = Depends(get_current_user),
    service: DashboardService = Depends(get_dashboard_service),
) -> DashboardSummaryResponse:
    """
    Retorna o resumo do dashboard.

    Inclui contagens de projetos ativos, jobs ativos/inativos,
    execucoes do dia por status e taxa de sucesso dos ultimos 7 dias.

    Requer autenticacao via access token.
    """
    return service.get_summary()


@router.get(
    '/recent-executions',
    response_model=list[RecentExecutionResponse],
)
def get_recent_executions(
    current_user: User = Depends(get_current_user),
    service: DashboardService = Depends(get_dashboard_service),
) -> list[RecentExecutionResponse]:
    """
    Retorna as ultimas 10 execucoes.

    Inclui nome do job, nome do projeto, status, timestamp e duracao.

    Requer autenticacao via access token.
    """
    return service.get_recent_executions()


@router.get(
    '/upcoming-executions',
    response_model=list[UpcomingExecutionResponse],
)
def get_upcoming_executions(
    current_user: User = Depends(get_current_user),
    service: DashboardService = Depends(get_dashboard_service),
) -> list[UpcomingExecutionResponse]:
    """
    Retorna as proximas 10 execucoes agendadas.

    Calcula o proximo disparo com base no cron de cada job ativo.

    Requer autenticacao via access token.
    """
    return service.get_upcoming_executions()


@router.get(
    '/recent-failures',
    response_model=list[RecentFailureResponse],
)
def get_recent_failures(
    current_user: User = Depends(get_current_user),
    service: DashboardService = Depends(get_dashboard_service),
) -> list[RecentFailureResponse]:
    """
    Retorna execucoes com falha das ultimas 24 horas.

    Inclui nome do job, nome do projeto, timestamp e resumo do erro.

    Requer autenticacao via access token.
    """
    return service.get_recent_failures()


@router.get('/token-usage', response_model=TokenUsageResponse)
def get_token_usage(
    date_from: datetime | None = Query(
        default=None,
        description='Inicio do periodo (ISO 8601). Default: 30 dias atras.',
    ),
    date_to: datetime | None = Query(
        default=None,
        description='Fim do periodo (ISO 8601). Default: agora.',
    ),
    provider: str | None = Query(
        default=None,
        description='Filtrar por provider (anthropic, openai, google, ollama).',
    ),
    current_user: User = Depends(get_current_user),
    service: DashboardService = Depends(get_dashboard_service),
) -> TokenUsageResponse:
    """
    Retorna consumo agregado de tokens LLM.

    Permite filtrar por periodo e provider. Retorna total de tokens,
    custo estimado, consumo por provider e media por chamada.

    Requer autenticacao via access token.
    """
    return service.get_token_usage(
        date_from=date_from,
        date_to=date_to,
        provider=provider,
    )
