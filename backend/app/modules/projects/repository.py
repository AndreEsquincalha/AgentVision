import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.projects.models import Project
from app.shared.utils import utc_now


class ProjectRepository:
    """
    Repositorio de acesso a dados de projetos.

    Responsavel por operacoes de leitura e escrita na tabela projects.
    Nao contem logica de negocio — apenas acesso a dados.
    """

    def __init__(self, db: Session) -> None:
        """Inicializa o repositorio com a sessao do banco."""
        self._db = db

    def get_all(
        self,
        page: int = 1,
        per_page: int = 20,
        search: str | None = None,
        is_active: bool | None = None,
    ) -> tuple[list[Project], int]:
        """
        Busca todos os projetos com paginacao e filtros.

        Args:
            page: Numero da pagina (1-indexed).
            per_page: Quantidade de itens por pagina.
            search: Termo de busca para filtrar por nome ou descricao.
            is_active: Filtro por status ativo/inativo.

        Returns:
            Tupla com lista de projetos e total de registros.
        """
        # Query base filtrando registros nao excluidos
        stmt = select(Project).where(Project.deleted_at.is_(None))
        count_stmt = select(func.count(Project.id)).where(Project.deleted_at.is_(None))

        # Filtro por busca textual (nome ou descricao)
        if search:
            search_filter = f'%{search}%'
            stmt = stmt.where(
                (Project.name.ilike(search_filter))
                | (Project.description.ilike(search_filter))
            )
            count_stmt = count_stmt.where(
                (Project.name.ilike(search_filter))
                | (Project.description.ilike(search_filter))
            )

        # Filtro por status ativo
        if is_active is not None:
            stmt = stmt.where(Project.is_active == is_active)
            count_stmt = count_stmt.where(Project.is_active == is_active)

        # Contagem total
        total: int = self._db.execute(count_stmt).scalar_one()

        # Paginacao e ordenacao
        offset = (page - 1) * per_page
        stmt = stmt.order_by(Project.created_at.desc()).offset(offset).limit(per_page)

        projects: list[Project] = list(self._db.execute(stmt).scalars().all())
        return projects, total

    def get_by_id(self, project_id: uuid.UUID) -> Project | None:
        """
        Busca um projeto pelo ID (excluindo registros com soft delete).

        Args:
            project_id: ID (UUID) do projeto.

        Returns:
            Projeto encontrado ou None.
        """
        stmt = select(Project).where(
            Project.id == project_id,
            Project.deleted_at.is_(None),
        )
        return self._db.execute(stmt).scalar_one_or_none()

    def create(self, project_data: dict) -> Project:
        """
        Cria um novo projeto no banco de dados.

        Args:
            project_data: Dicionario com os dados do projeto.

        Returns:
            Projeto criado.
        """
        project = Project(**project_data)
        self._db.add(project)
        self._db.commit()
        self._db.refresh(project)
        return project

    def update(self, project_id: uuid.UUID, project_data: dict) -> Project | None:
        """
        Atualiza um projeto existente.

        Args:
            project_id: ID (UUID) do projeto a ser atualizado.
            project_data: Dicionario com os campos a atualizar.

        Returns:
            Projeto atualizado ou None se nao encontrado.
        """
        project = self.get_by_id(project_id)
        if not project:
            return None

        for key, value in project_data.items():
            setattr(project, key, value)

        self._db.commit()
        self._db.refresh(project)
        return project

    def soft_delete(self, project_id: uuid.UUID) -> bool:
        """
        Realiza soft delete de um projeto (define deleted_at).

        Args:
            project_id: ID (UUID) do projeto a ser excluido.

        Returns:
            True se o projeto foi excluido, False se nao encontrado.
        """
        project = self.get_by_id(project_id)
        if not project:
            return False

        project.deleted_at = utc_now()
        project.is_active = False
        self._db.commit()
        return True

    def count_active(self) -> int:
        """
        Conta o numero de projetos ativos (nao excluidos).

        Returns:
            Quantidade de projetos ativos.
        """
        stmt = select(func.count(Project.id)).where(
            Project.deleted_at.is_(None),
            Project.is_active.is_(True),
        )
        return self._db.execute(stmt).scalar_one()
