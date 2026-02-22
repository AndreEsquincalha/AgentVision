from sqlalchemy.orm import Session

from app.modules.dashboard.schemas import (
    DashboardSummaryResponse,
    ExecutionStatusCounts,
    RecentExecutionResponse,
    RecentFailureResponse,
    UpcomingExecutionResponse,
)


class DashboardService:
    """
    Servico do dashboard.

    Contem a logica de negocio para agregar dados de resumo,
    execucoes recentes, proximas execucoes e falhas recentes.

    Atualmente retorna dados mock enquanto os modelos Project, Job
    e Execution ainda nao foram implementados. Sera substituido
    por consultas reais nos sprints posteriores.
    """

    def __init__(self, db: Session) -> None:
        """
        Inicializa o servico com a sessao do banco de dados.

        Args:
            db: Sessao do SQLAlchemy para acesso ao banco.
        """
        self._db = db

    def get_summary(self) -> DashboardSummaryResponse:
        """
        Retorna o resumo do dashboard com contagens e metricas.

        Inclui: projetos ativos, jobs ativos/inativos,
        execucoes do dia por status e taxa de sucesso (7 dias).

        Returns:
            DashboardSummaryResponse com os dados agregados.
        """
        # TODO: Substituir por consultas reais quando os modelos
        # Project, Job e Execution forem implementados (Sprint 4+)
        return DashboardSummaryResponse(
            active_projects=0,
            active_jobs=0,
            inactive_jobs=0,
            executions_today=ExecutionStatusCounts(
                pending=0,
                running=0,
                success=0,
                failed=0,
            ),
            success_rate=0.0,
        )

    def get_recent_executions(self) -> list[RecentExecutionResponse]:
        """
        Retorna as ultimas 10 execucoes ordenadas por data de inicio.

        Inclui nome do job, nome do projeto, status, timestamp e duracao.

        Returns:
            Lista de RecentExecutionResponse (vazia por enquanto).
        """
        # TODO: Substituir por consulta real quando o modelo Execution
        # estiver implementado, com join em Job e Project
        return []

    def get_upcoming_executions(self) -> list[UpcomingExecutionResponse]:
        """
        Retorna as proximas 10 execucoes agendadas.

        Calcula o proximo disparo com base na expressao cron de cada job ativo.

        Returns:
            Lista de UpcomingExecutionResponse (vazia por enquanto).
        """
        # TODO: Substituir por consulta real quando os modelos Job e Project
        # estiverem implementados, usando croniter para calcular next_run
        return []

    def get_recent_failures(self) -> list[RecentFailureResponse]:
        """
        Retorna execucoes com falha das ultimas 24 horas.

        Inclui nome do job, projeto, timestamp e resumo do erro.

        Returns:
            Lista de RecentFailureResponse (vazia por enquanto).
        """
        # TODO: Substituir por consulta real filtrando execucoes
        # com status='failed' e started_at >= now() - 24h
        return []
