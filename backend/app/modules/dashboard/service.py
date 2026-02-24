from datetime import timedelta

from croniter import croniter
from sqlalchemy.orm import Session

from app.modules.dashboard.schemas import (
    DashboardSummaryResponse,
    ExecutionStatusCounts,
    RecentExecutionResponse,
    RecentFailureResponse,
    UpcomingExecutionResponse,
)
from app.modules.executions.repository import ExecutionRepository
from app.modules.jobs.repository import JobRepository
from app.modules.projects.repository import ProjectRepository
from app.shared.utils import utc_now


class DashboardService:
    """
    Servico do dashboard.

    Contem a logica de negocio para agregar dados de resumo,
    execucoes recentes, proximas execucoes e falhas recentes.

    Agora utiliza consultas reais nos modelos Project, Job e Execution.
    """

    def __init__(self, db: Session) -> None:
        """
        Inicializa o servico com a sessao do banco de dados.

        Instancia os repositorios necessarios para consultas reais.

        Args:
            db: Sessao do SQLAlchemy para acesso ao banco.
        """
        self._db = db
        self._project_repository = ProjectRepository(db)
        self._job_repository = JobRepository(db)
        self._execution_repository = ExecutionRepository(db)

    def get_summary(self) -> DashboardSummaryResponse:
        """
        Retorna o resumo do dashboard com contagens e metricas reais.

        Inclui: projetos ativos, jobs ativos/inativos,
        execucoes do dia por status e taxa de sucesso (7 dias).

        Returns:
            DashboardSummaryResponse com os dados agregados.
        """
        # Contagem de projetos ativos
        active_projects = self._project_repository.count_active()

        # Contagem de jobs ativos e inativos
        active_jobs = self._job_repository.count_active()

        # Jobs inativos = total nao-excluidos - ativos
        all_jobs, total_jobs = self._job_repository.get_all(
            page=1, per_page=1,
        )
        inactive_jobs = total_jobs - active_jobs

        # Execucoes de hoje agrupadas por status
        now = utc_now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_counts = self._execution_repository.count_by_status(
            date_from=today_start,
            date_to=now,
        )

        # Taxa de sucesso dos ultimos 7 dias
        seven_days_ago = now - timedelta(days=7)
        total_7d = self._execution_repository.count_total(
            date_from=seven_days_ago,
            date_to=now,
        )
        success_7d = self._execution_repository.count_successful(
            date_from=seven_days_ago,
            date_to=now,
        )
        success_rate = (
            (success_7d / total_7d * 100) if total_7d > 0 else 0.0
        )

        executions_today = ExecutionStatusCounts(
            pending=today_counts.get('pending', 0),
            running=today_counts.get('running', 0),
            success=today_counts.get('success', 0),
            failed=today_counts.get('failed', 0),
        )

        # Total de execucoes hoje (soma de todos os status)
        today_total = (
            executions_today.pending
            + executions_today.running
            + executions_today.success
            + executions_today.failed
        )

        return DashboardSummaryResponse(
            active_projects=active_projects,
            active_jobs=active_jobs,
            inactive_jobs=inactive_jobs,
            executions_today=executions_today,
            success_rate=round(success_rate, 2),
            today_executions=today_total,
            today_success=executions_today.success,
            today_failed=executions_today.failed,
            today_running=executions_today.running,
            success_rate_7d=round(success_rate, 2),
        )

    def get_recent_executions(self) -> list[RecentExecutionResponse]:
        """
        Retorna as ultimas 10 execucoes ordenadas por data de criacao.

        Inclui nome do job, nome do projeto, status, timestamp e duracao.

        Returns:
            Lista de RecentExecutionResponse.
        """
        executions = self._execution_repository.get_recent(limit=10)

        results: list[RecentExecutionResponse] = []
        for execution in executions:
            job_name = ''
            project_name = ''

            if execution.job:
                job_name = execution.job.name
                if execution.job.project:
                    project_name = execution.job.project.name

            results.append(
                RecentExecutionResponse(
                    id=execution.id,
                    job_name=job_name,
                    project_name=project_name,
                    status=execution.status,
                    started_at=execution.started_at or execution.created_at,
                    duration_seconds=execution.duration_seconds,
                )
            )

        return results

    def get_upcoming_executions(self) -> list[UpcomingExecutionResponse]:
        """
        Retorna as proximas 10 execucoes agendadas.

        Calcula o proximo disparo com base na expressao cron de cada job ativo.

        Returns:
            Lista de UpcomingExecutionResponse ordenada por next_run.
        """
        active_jobs = self._job_repository.get_active_jobs()

        upcoming: list[UpcomingExecutionResponse] = []
        now = utc_now()

        for job in active_jobs:
            try:
                cron = croniter(job.cron_expression, now)
                next_run = cron.get_next(type(now))

                project_name = ''
                if job.project:
                    project_name = job.project.name

                upcoming.append(
                    UpcomingExecutionResponse(
                        job_id=job.id,
                        job_name=job.name,
                        project_name=project_name,
                        next_run=next_run,
                    )
                )
            except (ValueError, KeyError):
                # Ignora jobs com expressao cron invalida
                continue

        # Ordena por proximo disparo (mais proximo primeiro) e limita a 10
        upcoming.sort(key=lambda x: x.next_run)
        return upcoming[:10]

    def get_recent_failures(self) -> list[RecentFailureResponse]:
        """
        Retorna execucoes com falha das ultimas 24 horas.

        Inclui nome do job, projeto, timestamp e resumo do erro.

        Returns:
            Lista de RecentFailureResponse.
        """
        failed_executions = self._execution_repository.get_recent_by_status(
            status='failed',
            limit=10,
            hours=24,
        )

        results: list[RecentFailureResponse] = []
        for execution in failed_executions:
            job_name = ''
            project_name = ''

            if execution.job:
                job_name = execution.job.name
                if execution.job.project:
                    project_name = execution.job.project.name

            # Extrai resumo do erro dos logs (primeiras 200 chars)
            error_summary = 'Erro desconhecido'
            if execution.logs:
                error_summary = execution.logs[:200]
                if len(execution.logs) > 200:
                    error_summary += '...'

            results.append(
                RecentFailureResponse(
                    id=execution.id,
                    job_name=job_name,
                    project_name=project_name,
                    started_at=execution.started_at or execution.created_at,
                    error_summary=error_summary,
                )
            )

        return results
