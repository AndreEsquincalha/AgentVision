import uuid
from datetime import datetime

from sqlalchemy import delete as sa_delete, func, select
from sqlalchemy.orm import Session, joinedload

from app.modules.delivery.models import DeliveryLog
from app.modules.executions.models import Execution
from app.modules.jobs.models import Job


class ExecutionRepository:
    """
    Repositorio de acesso a dados de execucoes.

    Responsavel por operacoes de leitura e escrita na tabela executions.
    Nao contem logica de negocio — apenas acesso a dados.
    """

    def __init__(self, db: Session) -> None:
        """Inicializa o repositorio com a sessao do banco."""
        self._db = db

    def get_all(
        self,
        page: int = 1,
        per_page: int = 20,
        job_id: uuid.UUID | None = None,
        project_id: uuid.UUID | None = None,
        status: str | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
        is_dry_run: bool | None = None,
    ) -> tuple[list[Execution], int]:
        """
        Busca todas as execucoes com paginacao e filtros.

        Args:
            page: Numero da pagina (1-indexed).
            per_page: Quantidade de itens por pagina.
            job_id: Filtro por job.
            project_id: Filtro por projeto (via join com Job).
            status: Filtro por status (pending, running, success, failed).
            date_from: Filtro por data/hora de inicio minima.
            date_to: Filtro por data/hora de inicio maxima.
            is_dry_run: Filtro por execucao de teste.

        Returns:
            Tupla com lista de execucoes e total de registros.
        """
        # Query base com join em Job para acesso ao project_id
        stmt = select(Execution).join(Execution.job)
        count_stmt = select(func.count(Execution.id)).join(Execution.job)

        # Filtro por job
        if job_id is not None:
            stmt = stmt.where(Execution.job_id == job_id)
            count_stmt = count_stmt.where(Execution.job_id == job_id)

        # Filtro por projeto (via Job)
        if project_id is not None:
            stmt = stmt.where(Job.project_id == project_id)
            count_stmt = count_stmt.where(Job.project_id == project_id)

        # Filtro por status
        if status is not None:
            stmt = stmt.where(Execution.status == status)
            count_stmt = count_stmt.where(Execution.status == status)

        # Filtro por periodo (data de inicio)
        if date_from is not None:
            stmt = stmt.where(Execution.started_at >= date_from)
            count_stmt = count_stmt.where(Execution.started_at >= date_from)

        if date_to is not None:
            stmt = stmt.where(Execution.started_at <= date_to)
            count_stmt = count_stmt.where(Execution.started_at <= date_to)

        # Filtro por dry run
        if is_dry_run is not None:
            stmt = stmt.where(Execution.is_dry_run == is_dry_run)
            count_stmt = count_stmt.where(Execution.is_dry_run == is_dry_run)

        # Contagem total
        total: int = self._db.execute(count_stmt).scalar_one()

        # Paginacao e ordenacao (mais recentes primeiro)
        offset = (page - 1) * per_page
        stmt = stmt.order_by(Execution.created_at.desc()).offset(offset).limit(per_page)

        executions: list[Execution] = list(self._db.execute(stmt).scalars().all())
        return executions, total

    def get_by_id(self, execution_id: uuid.UUID) -> Execution | None:
        """
        Busca uma execucao pelo ID com eager loading de Job, Project e DeliveryLogs.

        Args:
            execution_id: ID (UUID) da execucao.

        Returns:
            Execucao encontrada ou None.
        """
        stmt = select(Execution).where(
            Execution.id == execution_id,
        ).options(
            joinedload(Execution.job).joinedload(Job.project),
            joinedload(Execution.delivery_logs),
        )
        return self._db.execute(stmt).unique().scalar_one_or_none()

    def get_by_job_id(
        self,
        job_id: uuid.UUID,
        limit: int = 10,
    ) -> list[Execution]:
        """
        Busca as ultimas execucoes de um job especifico.

        Args:
            job_id: ID (UUID) do job.
            limit: Numero maximo de execucoes retornadas.

        Returns:
            Lista de execucoes do job ordenadas por criacao (mais recente primeiro).
        """
        stmt = select(Execution).where(
            Execution.job_id == job_id,
        ).order_by(Execution.created_at.desc()).limit(limit)

        return list(self._db.execute(stmt).scalars().all())

    def get_previous_successful(
        self,
        job_id: uuid.UUID,
        current_execution_id: uuid.UUID,
    ) -> Execution | None:
        """
        Busca a execucao bem-sucedida anterior a uma execucao especifica.

        Usado para comparacao de dados extraidos (delivery condition on_change).

        Args:
            job_id: ID do job.
            current_execution_id: ID da execucao atual (para excluir).

        Returns:
            Execucao anterior bem-sucedida ou None.
        """
        stmt = (
            select(Execution)
            .where(
                Execution.job_id == job_id,
                Execution.id != current_execution_id,
                Execution.status == 'success',
                Execution.is_dry_run.is_(False),
            )
            .order_by(Execution.created_at.desc())
            .limit(1)
        )
        return self._db.execute(stmt).scalar_one_or_none()

    def create(self, execution_data: dict) -> Execution:
        """
        Cria uma nova execucao no banco de dados.

        Args:
            execution_data: Dicionario com os dados da execucao.

        Returns:
            Execucao criada.
        """
        execution = Execution(**execution_data)
        self._db.add(execution)
        self._db.commit()
        self._db.refresh(execution)
        return execution

    def delete(self, execution_id: uuid.UUID) -> bool:
        """
        Exclui permanentemente uma execucao e seus delivery logs associados.

        Execucoes usam BaseModel (sem soft delete), portanto a exclusao
        e definitiva. Os DeliveryLogs vinculados sao removidos antes
        da execucao para manter integridade referencial.

        Args:
            execution_id: ID (UUID) da execucao a ser excluida.

        Returns:
            True se a execucao foi encontrada e excluida, False caso contrario.
        """
        # Verifica se a execucao existe
        stmt = select(Execution).where(Execution.id == execution_id)
        execution = self._db.execute(stmt).scalar_one_or_none()
        if not execution:
            return False

        # Remove delivery logs associados
        delete_logs_stmt = sa_delete(DeliveryLog).where(
            DeliveryLog.execution_id == execution_id,
        )
        self._db.execute(delete_logs_stmt)

        # Remove a execucao
        self._db.delete(execution)
        self._db.commit()
        return True

    def update_status(
        self,
        execution_id: uuid.UUID,
        status: str,
        logs: str | None = None,
        extracted_data: dict | None = None,
        screenshots_path: str | None = None,
        pdf_path: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        duration_seconds: int | None = None,
    ) -> Execution | None:
        """
        Atualiza o status e dados de uma execucao.

        Apenas campos com valores nao-None sao atualizados
        (exceto status, que e sempre atualizado).

        Args:
            execution_id: ID (UUID) da execucao.
            status: Novo status da execucao.
            logs: Logs de execucao.
            extracted_data: Dados extraidos (JSON).
            screenshots_path: Caminho dos screenshots no storage.
            pdf_path: Caminho do PDF no storage.
            started_at: Data/hora de inicio.
            finished_at: Data/hora de fim.
            duration_seconds: Duracao em segundos.

        Returns:
            Execucao atualizada ou None se nao encontrada.
        """
        stmt = select(Execution).where(Execution.id == execution_id)
        execution = self._db.execute(stmt).scalar_one_or_none()
        if not execution:
            return None

        # Status sempre e atualizado
        execution.status = status

        # Demais campos sao atualizados somente se fornecidos
        if logs is not None:
            execution.logs = logs
        if extracted_data is not None:
            execution.extracted_data = extracted_data
        if screenshots_path is not None:
            execution.screenshots_path = screenshots_path
        if pdf_path is not None:
            execution.pdf_path = pdf_path
        if started_at is not None:
            execution.started_at = started_at
        if finished_at is not None:
            execution.finished_at = finished_at
        if duration_seconds is not None:
            execution.duration_seconds = duration_seconds

        self._db.commit()
        self._db.refresh(execution)
        return execution

    def update_progress(
        self,
        execution_id: uuid.UUID,
        progress_percent: int,
        logs: str | None = None,
    ) -> Execution | None:
        """
        Atualiza o progresso percentual de uma execucao.

        Opcionalmente atualiza os logs junto com o progresso.

        Args:
            execution_id: ID (UUID) da execucao.
            progress_percent: Valor de progresso (0-100).
            logs: Logs atualizados (opcional).

        Returns:
            Execucao atualizada ou None se nao encontrada.
        """
        stmt = select(Execution).where(Execution.id == execution_id)
        execution = self._db.execute(stmt).scalar_one_or_none()
        if not execution:
            return None

        execution.progress_percent = max(0, min(100, progress_percent))

        if logs is not None:
            execution.logs = logs

        self._db.commit()
        self._db.refresh(execution)
        return execution

    def count_by_status(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> dict[str, int]:
        """
        Conta execucoes agrupadas por status em um periodo.

        Args:
            date_from: Data/hora de inicio do periodo.
            date_to: Data/hora de fim do periodo.

        Returns:
            Dicionario com contagens por status
            (pending, running, success, failed, cancelled).
        """
        stmt = select(
            Execution.status,
            func.count(Execution.id),
        )

        if date_from is not None:
            stmt = stmt.where(Execution.created_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(Execution.created_at <= date_to)

        stmt = stmt.group_by(Execution.status)

        results = self._db.execute(stmt).all()

        # Inicializa com zeros para todos os status possiveis
        counts: dict[str, int] = {
            'pending': 0,
            'running': 0,
            'success': 0,
            'failed': 0,
            'cancelled': 0,
        }

        for status_value, count in results:
            if status_value in counts:
                counts[status_value] = count

        return counts

    def get_recent(self, limit: int = 10) -> list[Execution]:
        """
        Busca as execucoes mais recentes.

        Args:
            limit: Numero maximo de execucoes retornadas.

        Returns:
            Lista de execucoes ordenadas por criacao (mais recente primeiro).
        """
        stmt = select(Execution).options(
            joinedload(Execution.job).joinedload(Job.project),
        ).order_by(
            Execution.created_at.desc(),
        ).limit(limit)

        return list(self._db.execute(stmt).unique().scalars().all())

    def get_recent_by_status(
        self,
        status: str,
        limit: int = 10,
        hours: int | None = None,
    ) -> list[Execution]:
        """
        Busca execucoes recentes com um status especifico.

        Args:
            status: Status a filtrar (pending, running, success, failed).
            limit: Numero maximo de execucoes retornadas.
            hours: Se fornecido, limita a execucoes das ultimas N horas.

        Returns:
            Lista de execucoes filtradas por status.
        """
        from app.shared.utils import utc_now
        from datetime import timedelta

        stmt = select(Execution).options(
            joinedload(Execution.job).joinedload(Job.project),
        ).where(
            Execution.status == status,
        )

        if hours is not None:
            cutoff = utc_now() - timedelta(hours=hours)
            stmt = stmt.where(Execution.created_at >= cutoff)

        stmt = stmt.order_by(Execution.created_at.desc()).limit(limit)

        return list(self._db.execute(stmt).unique().scalars().all())

    def count_total(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> int:
        """
        Conta o total de execucoes em um periodo.

        Args:
            date_from: Data/hora de inicio do periodo.
            date_to: Data/hora de fim do periodo.

        Returns:
            Total de execucoes no periodo.
        """
        stmt = select(func.count(Execution.id))

        if date_from is not None:
            stmt = stmt.where(Execution.created_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(Execution.created_at <= date_to)

        return self._db.execute(stmt).scalar_one()

    def count_successful(
        self,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> int:
        """
        Conta execucoes com sucesso em um periodo.

        Args:
            date_from: Data/hora de inicio do periodo.
            date_to: Data/hora de fim do periodo.

        Returns:
            Total de execucoes com sucesso no periodo.
        """
        stmt = select(func.count(Execution.id)).where(
            Execution.status == 'success',
        )

        if date_from is not None:
            stmt = stmt.where(Execution.created_at >= date_from)
        if date_to is not None:
            stmt = stmt.where(Execution.created_at <= date_to)

        return self._db.execute(stmt).scalar_one()
