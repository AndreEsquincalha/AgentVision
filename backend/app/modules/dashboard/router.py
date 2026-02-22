from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.dashboard.schemas import (
    DashboardSummaryResponse,
    RecentExecutionResponse,
    RecentFailureResponse,
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
