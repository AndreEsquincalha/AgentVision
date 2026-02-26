from datetime import datetime, timedelta

from croniter import croniter
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.shared.cache import cached

from app.modules.dashboard.schemas import (
    CeleryWorkerStatusResponse,
    DashboardSummaryResponse,
    DurationByJobResponse,
    ExecutionStatusCounts,
    ExecutionsPerHourResponse,
    OperationalMetricsResponse,
    ProviderUsageResponse,
    RecentExecutionResponse,
    RecentFailureResponse,
    TokenUsageResponse,
    UpcomingExecutionResponse,
)
from app.modules.executions.models import Execution
from app.modules.executions.repository import ExecutionRepository
from app.modules.jobs.models import Job
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

    @cached(ttl=60, prefix='dashboard:summary')
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

    @cached(ttl=30, prefix='dashboard:recent_executions')
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

    @cached(ttl=300, prefix='dashboard:upcoming')
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

    @cached(ttl=60, prefix='dashboard:failures')
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

    def get_token_usage(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        provider: str | None = None,
    ) -> TokenUsageResponse:
        """
        Retorna consumo agregado de tokens LLM por provider e periodo.

        Args:
            date_from: Inicio do periodo (inclusive). Default: 30 dias atras.
            date_to: Fim do periodo (inclusive). Default: agora.
            provider: Filtro por provider (opcional).

        Returns:
            TokenUsageResponse com totais e desdobramento por provider.
        """
        from app.modules.agents.token_tracker import TokenTracker

        now = utc_now()
        if date_from is None:
            date_from = now - timedelta(days=30)
        if date_to is None:
            date_to = now

        usage_data = TokenTracker.get_usage_for_period(
            date_from=date_from,
            date_to=date_to,
            provider=provider,
        )

        # Agrega totais
        total_tokens = 0
        total_input = 0
        total_output = 0
        total_cost = 0.0
        total_images = 0
        total_calls = 0

        by_provider: list[ProviderUsageResponse] = []

        for row in usage_data:
            total_tokens += row['total_tokens']
            total_input += row['total_input_tokens']
            total_output += row['total_output_tokens']
            total_cost += row['estimated_cost_usd']
            total_images += row['total_images']
            total_calls += row['call_count']

            by_provider.append(ProviderUsageResponse(
                provider=row['provider'],
                total_input_tokens=row['total_input_tokens'],
                total_output_tokens=row['total_output_tokens'],
                total_tokens=row['total_tokens'],
                total_images=row['total_images'],
                estimated_cost_usd=round(row['estimated_cost_usd'], 6),
                call_count=row['call_count'],
            ))

        avg_per_call = (
            (total_tokens / total_calls) if total_calls > 0 else 0.0
        )

        return TokenUsageResponse(
            total_tokens=total_tokens,
            total_input_tokens=total_input,
            total_output_tokens=total_output,
            estimated_cost_usd=round(total_cost, 6),
            total_images=total_images,
            total_calls=total_calls,
            avg_tokens_per_call=round(avg_per_call, 1),
            usage_by_provider=by_provider,
        )

    @cached(ttl=60, prefix='dashboard:operational')
    def get_operational_metrics(self) -> OperationalMetricsResponse:
        """
        Retorna metricas operacionais para o dashboard avancado.

        Inclui execucoes por hora (24h), duracao media por job (top 10),
        status dos workers Celery e tokens do dia.
        """
        now = utc_now()

        # --- Execucoes por hora (ultimas 24h) ---
        hours_ago_24 = now - timedelta(hours=24)
        executions_per_hour = self._get_executions_per_hour(hours_ago_24, now)

        # --- Duracao media por job (top 10, ultimos 7 dias) ---
        seven_days_ago = now - timedelta(days=7)
        duration_by_job = self._get_duration_by_job(seven_days_ago, now)

        # --- Status dos workers Celery ---
        workers = self._get_celery_workers_status()

        # --- Tokens do dia ---
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        from app.modules.agents.token_tracker import TokenTracker
        total_tokens_today = TokenTracker.get_total_tokens_for_period(
            date_from=today_start,
            date_to=now,
        )

        # --- Duracao media hoje ---
        avg_stmt = select(func.avg(Execution.duration_seconds)).where(
            Execution.created_at >= today_start,
            Execution.created_at <= now,
            Execution.duration_seconds.isnot(None),
        )
        avg_duration = self._db.execute(avg_stmt).scalar() or 0.0

        return OperationalMetricsResponse(
            executions_per_hour=executions_per_hour,
            duration_by_job=duration_by_job,
            workers=workers,
            total_tokens_today=total_tokens_today,
            avg_duration_today=round(float(avg_duration), 1),
        )

    def _get_executions_per_hour(
        self,
        date_from: datetime,
        date_to: datetime,
    ) -> list[ExecutionsPerHourResponse]:
        """Retorna contagem de execucoes agrupadas por hora."""
        from sqlalchemy import case, extract

        # Agrupa por hora truncada
        hour_expr = func.date_trunc('hour', Execution.created_at)

        stmt = select(
            hour_expr.label('hour'),
            func.count(Execution.id).label('total'),
            func.count(case(
                (Execution.status == 'success', 1),
            )).label('success'),
            func.count(case(
                (Execution.status == 'failed', 1),
            )).label('failed'),
        ).where(
            Execution.created_at >= date_from,
            Execution.created_at <= date_to,
        ).group_by('hour').order_by('hour')

        rows = self._db.execute(stmt).all()

        return [
            ExecutionsPerHourResponse(
                hour=row.hour.isoformat() if row.hour else '',
                total=row.total,
                success=row.success,
                failed=row.failed,
            )
            for row in rows
        ]

    def _get_duration_by_job(
        self,
        date_from: datetime,
        date_to: datetime,
    ) -> list[DurationByJobResponse]:
        """Retorna duracao media de execucao por job (top 10)."""
        stmt = select(
            Execution.job_id,
            Job.name.label('job_name'),
            func.avg(Execution.duration_seconds).label('avg_duration'),
            func.count(Execution.id).label('exec_count'),
        ).join(
            Job, Execution.job_id == Job.id,
        ).where(
            Execution.created_at >= date_from,
            Execution.created_at <= date_to,
            Execution.duration_seconds.isnot(None),
            Execution.status == 'success',
        ).group_by(
            Execution.job_id, Job.name,
        ).order_by(
            func.avg(Execution.duration_seconds).desc(),
        ).limit(10)

        rows = self._db.execute(stmt).all()

        return [
            DurationByJobResponse(
                job_id=row.job_id,
                job_name=row.job_name,
                avg_duration_seconds=round(float(row.avg_duration), 1),
                execution_count=row.exec_count,
            )
            for row in rows
        ]

    @staticmethod
    def _get_celery_workers_status() -> list[CeleryWorkerStatusResponse]:
        """Retorna status dos workers Celery."""
        try:
            from app.celery_app import celery_app as _celery

            inspector = _celery.control.inspect(timeout=3.0)
            ping_result = inspector.ping() or {}
            active_result = inspector.active() or {}

            workers: list[CeleryWorkerStatusResponse] = []
            for name in ping_result:
                active_tasks = len(active_result.get(name, []))
                workers.append(CeleryWorkerStatusResponse(
                    name=name,
                    status='online',
                    active_tasks=active_tasks,
                ))

            return workers
        except Exception:
            return []
