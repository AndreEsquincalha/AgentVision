import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.prompts.models import PromptTemplate
from app.shared.utils import utc_now


class PromptTemplateRepository:
    """
    Repositorio de acesso a dados de templates de prompt.

    Responsavel por operacoes de leitura e escrita na tabela prompt_templates.
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
        category: str | None = None,
    ) -> tuple[list[PromptTemplate], int]:
        """
        Busca todos os templates com paginacao e filtros.

        Args:
            page: Numero da pagina (1-indexed).
            per_page: Quantidade de itens por pagina.
            search: Termo de busca para filtrar por nome ou descricao.
            category: Filtro por categoria.

        Returns:
            Tupla com lista de templates e total de registros.
        """
        # Query base filtrando registros nao excluidos
        stmt = select(PromptTemplate).where(PromptTemplate.deleted_at.is_(None))
        count_stmt = select(func.count(PromptTemplate.id)).where(
            PromptTemplate.deleted_at.is_(None)
        )

        # Filtro por busca textual (nome ou descricao)
        if search:
            search_filter = f'%{search}%'
            stmt = stmt.where(
                (PromptTemplate.name.ilike(search_filter))
                | (PromptTemplate.description.ilike(search_filter))
            )
            count_stmt = count_stmt.where(
                (PromptTemplate.name.ilike(search_filter))
                | (PromptTemplate.description.ilike(search_filter))
            )

        # Filtro por categoria
        if category:
            stmt = stmt.where(PromptTemplate.category == category)
            count_stmt = count_stmt.where(PromptTemplate.category == category)

        # Contagem total
        total: int = self._db.execute(count_stmt).scalar_one()

        # Paginacao e ordenacao
        offset = (page - 1) * per_page
        stmt = stmt.order_by(PromptTemplate.created_at.desc()).offset(offset).limit(per_page)

        templates: list[PromptTemplate] = list(self._db.execute(stmt).scalars().all())
        return templates, total

    def get_by_id(self, template_id: uuid.UUID) -> PromptTemplate | None:
        """
        Busca um template pelo ID (excluindo registros com soft delete).

        Args:
            template_id: ID (UUID) do template.

        Returns:
            Template encontrado ou None.
        """
        stmt = select(PromptTemplate).where(
            PromptTemplate.id == template_id,
            PromptTemplate.deleted_at.is_(None),
        )
        return self._db.execute(stmt).scalar_one_or_none()

    def create(self, template_data: dict) -> PromptTemplate:
        """
        Cria um novo template no banco de dados.

        Args:
            template_data: Dicionario com os dados do template.

        Returns:
            Template criado.
        """
        template = PromptTemplate(**template_data)
        self._db.add(template)
        self._db.commit()
        self._db.refresh(template)
        return template

    def update(self, template_id: uuid.UUID, template_data: dict) -> PromptTemplate | None:
        """
        Atualiza um template existente.

        Args:
            template_id: ID (UUID) do template a ser atualizado.
            template_data: Dicionario com os campos a atualizar.

        Returns:
            Template atualizado ou None se nao encontrado.
        """
        template = self.get_by_id(template_id)
        if not template:
            return None

        for key, value in template_data.items():
            setattr(template, key, value)

        self._db.commit()
        self._db.refresh(template)
        return template

    def soft_delete(self, template_id: uuid.UUID) -> bool:
        """
        Realiza soft delete de um template (define deleted_at).

        Args:
            template_id: ID (UUID) do template a ser excluido.

        Returns:
            True se o template foi excluido, False se nao encontrado.
        """
        template = self.get_by_id(template_id)
        if not template:
            return False

        template.deleted_at = utc_now()
        self._db.commit()
        return True

    def count_all(self) -> int:
        """
        Conta o numero total de templates ativos (nao excluidos).

        Returns:
            Quantidade de templates ativos.
        """
        stmt = select(func.count(PromptTemplate.id)).where(
            PromptTemplate.deleted_at.is_(None)
        )
        return self._db.execute(stmt).scalar_one()
