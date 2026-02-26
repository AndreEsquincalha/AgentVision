from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.modules.auth.models import User
from app.modules.dashboard.schemas import (
    DashboardSummaryResponse,
    LLMProviderHealthListResponse,
    LLMProviderHealthResponse,
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
    current_user: User = Depends(require_roles('admin', 'operator', 'viewer')),
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
    current_user: User = Depends(require_roles('admin', 'operator', 'viewer')),
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
    current_user: User = Depends(require_roles('admin', 'operator', 'viewer')),
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
    current_user: User = Depends(require_roles('admin', 'operator', 'viewer')),
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
    current_user: User = Depends(require_roles('admin', 'operator', 'viewer')),
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


@router.get('/llm-providers-health', response_model=LLMProviderHealthListResponse)
def get_llm_providers_health(
    current_user: User = Depends(require_roles('admin', 'operator', 'viewer')),
) -> LLMProviderHealthListResponse:
    """
    Retorna o status de saude dos providers LLM.

    Inclui latencia, disponibilidade e estado do circuit breaker
    para cada provider. Os dados vem do ultimo health check periodico.

    Requer autenticacao via access token.
    """
    from app.modules.agents.llm_resilience import (
        circuit_breaker,
        get_all_health_statuses,
    )

    health_statuses = get_all_health_statuses()
    cb_states = circuit_breaker.get_all_states()

    providers = [
        LLMProviderHealthResponse(
            provider=s['provider'],
            status=s['status'],
            latency_ms=s['latency_ms'],
            last_check=s['last_check'],
            error=s.get('error'),
        )
        for s in health_statuses
    ]

    circuit_breaker_map = {
        name: state.state
        for name, state in cb_states.items()
    }

    return LLMProviderHealthListResponse(
        providers=providers,
        circuit_breakers=circuit_breaker_map,
    )


@router.get('/ollama-models', response_model=list[dict])
def get_ollama_models(
    ollama_url: str = Query(
        default='http://localhost:11434',
        description='URL do servidor Ollama',
    ),
    current_user: User = Depends(require_roles('admin', 'operator')),
) -> list[dict]:
    """
    Lista modelos disponiveis no servidor Ollama (13.3.2).

    Retorna nome, tamanho e se o modelo tem suporte a visao.
    """
    from app.modules.agents.llm_provider import OllamaProvider

    provider = OllamaProvider(
        api_key=ollama_url,
        model='',
    )
    return provider.list_models()
