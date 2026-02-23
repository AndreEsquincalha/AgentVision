import uuid

from app.modules.prompts.repository import PromptTemplateRepository
from app.modules.prompts.schemas import (
    PromptTemplateCreate,
    PromptTemplateResponse,
    PromptTemplateUpdate,
)
from app.shared.exceptions import NotFoundException
from app.shared.schemas import PaginatedResponse


class PromptTemplateService:
    """
    Servico de templates de prompt.

    Contem a logica de negocio para operacoes CRUD de templates,
    incluindo o versionamento automatico a cada atualizacao.
    """

    def __init__(self, repository: PromptTemplateRepository) -> None:
        """Inicializa o servico com o repositorio de templates."""
        self._repository = repository

    def list_templates(
        self,
        page: int = 1,
        per_page: int = 20,
        search: str | None = None,
        category: str | None = None,
    ) -> PaginatedResponse[PromptTemplateResponse]:
        """
        Lista templates com paginacao e filtros.

        Args:
            page: Numero da pagina.
            per_page: Itens por pagina.
            search: Termo de busca (nome ou descricao).
            category: Filtro por categoria.

        Returns:
            Resposta paginada com lista de templates.
        """
        templates, total = self._repository.get_all(
            page=page,
            per_page=per_page,
            search=search,
            category=category,
        )

        template_responses = [
            PromptTemplateResponse.model_validate(template)
            for template in templates
        ]

        return PaginatedResponse[PromptTemplateResponse].create(
            items=template_responses,
            total=total,
            page=page,
            per_page=per_page,
        )

    def get_template(self, template_id: uuid.UUID) -> PromptTemplateResponse:
        """
        Busca um template pelo ID.

        Args:
            template_id: ID do template.

        Returns:
            Dados do template.

        Raises:
            NotFoundException: Se o template nao for encontrado.
        """
        template = self._repository.get_by_id(template_id)
        if not template:
            raise NotFoundException('Template de prompt nao encontrado')
        return PromptTemplateResponse.model_validate(template)

    def create_template(self, data: PromptTemplateCreate) -> PromptTemplateResponse:
        """
        Cria um novo template de prompt.

        Args:
            data: Dados do template a ser criado.

        Returns:
            Dados do template criado.
        """
        template_data: dict = {
            'name': data.name,
            'content': data.content,
            'description': data.description,
            'category': data.category,
            'version': 1,
        }

        template = self._repository.create(template_data)
        return PromptTemplateResponse.model_validate(template)

    def update_template(
        self,
        template_id: uuid.UUID,
        data: PromptTemplateUpdate,
    ) -> PromptTemplateResponse:
        """
        Atualiza um template existente.

        Incrementa automaticamente o campo version a cada atualizacao.

        Args:
            template_id: ID do template a ser atualizado.
            data: Dados a serem atualizados.

        Returns:
            Dados do template atualizado.

        Raises:
            NotFoundException: Se o template nao for encontrado.
        """
        # Verifica se o template existe e obtem a versao atual
        existing = self._repository.get_by_id(template_id)
        if not existing:
            raise NotFoundException('Template de prompt nao encontrado')

        # Prepara dados de atualizacao (apenas campos fornecidos)
        update_data: dict = {}

        if data.content is not None:
            update_data['content'] = data.content

        if data.description is not None:
            update_data['description'] = data.description

        if data.category is not None:
            update_data['category'] = data.category

        # Se nao ha campos para atualizar, retorna o template atual
        if not update_data:
            return PromptTemplateResponse.model_validate(existing)

        # Incrementa a versao a cada atualizacao
        update_data['version'] = existing.version + 1

        template = self._repository.update(template_id, update_data)
        if not template:
            raise NotFoundException('Template de prompt nao encontrado')

        return PromptTemplateResponse.model_validate(template)

    def delete_template(self, template_id: uuid.UUID) -> None:
        """
        Realiza soft delete de um template.

        Args:
            template_id: ID do template a ser excluido.

        Raises:
            NotFoundException: Se o template nao for encontrado.
        """
        success = self._repository.soft_delete(template_id)
        if not success:
            raise NotFoundException('Template de prompt nao encontrado')
