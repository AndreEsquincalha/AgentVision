import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.jobs.models import Job
from app.shared.utils import utc_now


class JobRepository:
    """
    Repositorio de acesso a dados de jobs.

    Responsavel por operacoes de leitura e escrita na tabela jobs.
    Nao contem logica de negocio — apenas acesso a dados.
    """

    def __init__(self, db: Session) -> None:
        """Inicializa o repositorio com a sessao do banco."""
        self._db = db

    def get_all(
        self,
        page: int = 1,
        per_page: int = 20,
        project_id: uuid.UUID | None = None,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> tuple[list[Job], int]:
        """
        Busca todos os jobs com paginacao e filtros.

        Args:
            page: Numero da pagina (1-indexed).
            per_page: Quantidade de itens por pagina.
            project_id: Filtro por projeto.
            is_active: Filtro por status ativo/inativo.
            search: Termo de busca para filtrar por nome.

        Returns:
            Tupla com lista de jobs e total de registros.
        """
        # Query base filtrando registros nao excluidos
        stmt = select(Job).where(Job.deleted_at.is_(None))
        count_stmt = select(func.count(Job.id)).where(Job.deleted_at.is_(None))

        # Filtro por projeto
        if project_id is not None:
            stmt = stmt.where(Job.project_id == project_id)
            count_stmt = count_stmt.where(Job.project_id == project_id)

        # Filtro por status ativo
        if is_active is not None:
            stmt = stmt.where(Job.is_active == is_active)
            count_stmt = count_stmt.where(Job.is_active == is_active)

        # Filtro por busca textual (nome)
        if search:
            search_filter = f'%{search}%'
            stmt = stmt.where(Job.name.ilike(search_filter))
            count_stmt = count_stmt.where(Job.name.ilike(search_filter))

        # Contagem total
        total: int = self._db.execute(count_stmt).scalar_one()

        # Paginacao e ordenacao
        offset = (page - 1) * per_page
        stmt = stmt.order_by(Job.created_at.desc()).offset(offset).limit(per_page)

        jobs: list[Job] = list(self._db.execute(stmt).scalars().all())
        return jobs, total

    def get_by_id(self, job_id: uuid.UUID) -> Job | None:
        """
        Busca um job pelo ID (excluindo registros com soft delete).

        Args:
            job_id: ID (UUID) do job.

        Returns:
            Job encontrado ou None.
        """
        stmt = select(Job).where(
            Job.id == job_id,
            Job.deleted_at.is_(None),
        )
        return self._db.execute(stmt).scalar_one_or_none()

    def get_by_project_id(self, project_id: uuid.UUID) -> list[Job]:
        """
        Busca todos os jobs de um projeto especifico.

        Args:
            project_id: ID (UUID) do projeto.

        Returns:
            Lista de jobs do projeto.
        """
        stmt = select(Job).where(
            Job.project_id == project_id,
            Job.deleted_at.is_(None),
        ).order_by(Job.created_at.desc())

        return list(self._db.execute(stmt).scalars().all())

    def create(self, job_data: dict) -> Job:
        """
        Cria um novo job no banco de dados.

        Args:
            job_data: Dicionario com os dados do job.

        Returns:
            Job criado.
        """
        job = Job(**job_data)
        self._db.add(job)
        self._db.commit()
        self._db.refresh(job)
        return job

    def update(self, job_id: uuid.UUID, job_data: dict) -> Job | None:
        """
        Atualiza um job existente.

        Args:
            job_id: ID (UUID) do job a ser atualizado.
            job_data: Dicionario com os campos a atualizar.

        Returns:
            Job atualizado ou None se nao encontrado.
        """
        job = self.get_by_id(job_id)
        if not job:
            return None

        for key, value in job_data.items():
            setattr(job, key, value)

        self._db.commit()
        self._db.refresh(job)
        return job

    def soft_delete(self, job_id: uuid.UUID) -> bool:
        """
        Realiza soft delete de um job (define deleted_at).

        Args:
            job_id: ID (UUID) do job a ser excluido.

        Returns:
            True se o job foi excluido, False se nao encontrado.
        """
        job = self.get_by_id(job_id)
        if not job:
            return False

        job.deleted_at = utc_now()
        job.is_active = False
        self._db.commit()
        return True

    def get_active_jobs(self) -> list[Job]:
        """
        Busca todos os jobs ativos (nao excluidos e com is_active=True).

        Returns:
            Lista de jobs ativos.
        """
        stmt = select(Job).where(
            Job.deleted_at.is_(None),
            Job.is_active.is_(True),
        ).order_by(Job.created_at.desc())

        return list(self._db.execute(stmt).scalars().all())

    def count_active(self) -> int:
        """
        Conta o numero de jobs ativos (nao excluidos).

        Returns:
            Quantidade de jobs ativos.
        """
        stmt = select(func.count(Job.id)).where(
            Job.deleted_at.is_(None),
            Job.is_active.is_(True),
        )
        return self._db.execute(stmt).scalar_one()
