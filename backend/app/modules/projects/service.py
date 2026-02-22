import json
import uuid

from app.modules.projects.models import Project
from app.modules.projects.repository import ProjectRepository
from app.modules.projects.schemas import (
    ProjectCreate,
    ProjectListResponse,
    ProjectResponse,
    ProjectUpdate,
)
from app.shared.exceptions import NotFoundException
from app.shared.schemas import PaginatedResponse
from app.shared.utils import decrypt_value, encrypt_value


class ProjectService:
    """
    Servico de projetos.

    Contem a logica de negocio para operacoes CRUD de projetos,
    incluindo criptografia de campos sensiveis (credenciais e chave de API).
    """

    def __init__(self, repository: ProjectRepository) -> None:
        """Inicializa o servico com o repositorio de projetos."""
        self._repository = repository

    def list_projects(
        self,
        page: int = 1,
        per_page: int = 20,
        search: str | None = None,
        is_active: bool | None = None,
    ) -> PaginatedResponse[ProjectResponse]:
        """
        Lista projetos com paginacao e filtros.

        Args:
            page: Numero da pagina.
            per_page: Itens por pagina.
            search: Termo de busca (nome ou descricao).
            is_active: Filtro por status ativo/inativo.

        Returns:
            Resposta paginada com lista de projetos.
        """
        projects, total = self._repository.get_all(
            page=page,
            per_page=per_page,
            search=search,
            is_active=is_active,
        )

        project_responses = [
            ProjectResponse.from_model(project) for project in projects
        ]

        return PaginatedResponse[ProjectResponse].create(
            items=project_responses,
            total=total,
            page=page,
            per_page=per_page,
        )

    def get_project(self, project_id: uuid.UUID) -> ProjectResponse:
        """
        Busca um projeto pelo ID.

        Args:
            project_id: ID do projeto.

        Returns:
            Dados do projeto.

        Raises:
            NotFoundException: Se o projeto nao for encontrado.
        """
        project = self._repository.get_by_id(project_id)
        if not project:
            raise NotFoundException('Projeto nao encontrado')
        return ProjectResponse.from_model(project)

    def create_project(self, data: ProjectCreate) -> ProjectResponse:
        """
        Cria um novo projeto.

        Criptografa credenciais e chave de API antes de salvar.

        Args:
            data: Dados do projeto a ser criado.

        Returns:
            Dados do projeto criado.
        """
        project_data = self._prepare_project_data(data)
        project = self._repository.create(project_data)
        return ProjectResponse.from_model(project)

    def update_project(
        self,
        project_id: uuid.UUID,
        data: ProjectUpdate,
    ) -> ProjectResponse:
        """
        Atualiza um projeto existente.

        Criptografa credenciais e chave de API se fornecidos.

        Args:
            project_id: ID do projeto a ser atualizado.
            data: Dados a serem atualizados.

        Returns:
            Dados do projeto atualizado.

        Raises:
            NotFoundException: Se o projeto nao for encontrado.
        """
        # Verifica se o projeto existe
        existing = self._repository.get_by_id(project_id)
        if not existing:
            raise NotFoundException('Projeto nao encontrado')

        update_data = self._prepare_update_data(data)

        # Se nao ha campos para atualizar, retorna o projeto atual
        if not update_data:
            return ProjectResponse.from_model(existing)

        project = self._repository.update(project_id, update_data)
        if not project:
            raise NotFoundException('Projeto nao encontrado')

        return ProjectResponse.from_model(project)

    def delete_project(self, project_id: uuid.UUID) -> None:
        """
        Realiza soft delete de um projeto.

        Args:
            project_id: ID do projeto a ser excluido.

        Raises:
            NotFoundException: Se o projeto nao for encontrado.
        """
        success = self._repository.soft_delete(project_id)
        if not success:
            raise NotFoundException('Projeto nao encontrado')

    def get_decrypted_credentials(self, project_id: uuid.UUID) -> dict | None:
        """
        Obtem as credenciais descriptografadas de um projeto.

        Uso interno: chamado pelo agente de automacao para fazer login no site.

        Args:
            project_id: ID do projeto.

        Returns:
            Dicionario com credenciais ou None se nao configuradas.

        Raises:
            NotFoundException: Se o projeto nao for encontrado.
        """
        project = self._repository.get_by_id(project_id)
        if not project:
            raise NotFoundException('Projeto nao encontrado')

        if not project.encrypted_credentials:
            return None

        decrypted = decrypt_value(project.encrypted_credentials)
        return json.loads(decrypted)

    def get_llm_config(self, project_id: uuid.UUID) -> dict:
        """
        Obtem a configuracao completa do LLM de um projeto, com a API key descriptografada.

        Uso interno: chamado pelo VisionAnalyzer para configurar o provedor LLM.

        Args:
            project_id: ID do projeto.

        Returns:
            Dicionario com configuracoes do LLM (provider, model, api_key, temperature,
            max_tokens, timeout).

        Raises:
            NotFoundException: Se o projeto nao for encontrado.
        """
        project = self._repository.get_by_id(project_id)
        if not project:
            raise NotFoundException('Projeto nao encontrado')

        llm_config: dict = {
            'provider': project.llm_provider,
            'model': project.llm_model,
            'api_key': None,
            'temperature': project.llm_temperature,
            'max_tokens': project.llm_max_tokens,
            'timeout': project.llm_timeout,
        }

        if project.encrypted_llm_api_key:
            llm_config['api_key'] = decrypt_value(project.encrypted_llm_api_key)

        return llm_config

    # -------------------------------------------------------------------------
    # Metodos auxiliares privados
    # -------------------------------------------------------------------------

    def _prepare_project_data(self, data: ProjectCreate) -> dict:
        """
        Prepara os dados para criacao de projeto, criptografando campos sensiveis.

        Args:
            data: Dados do schema de criacao.

        Returns:
            Dicionario pronto para salvar no banco.
        """
        project_data: dict = {
            'name': data.name,
            'base_url': data.base_url,
            'description': data.description,
            'llm_provider': data.llm_provider,
            'llm_model': data.llm_model,
            'llm_temperature': data.llm_temperature,
            'llm_max_tokens': data.llm_max_tokens,
            'llm_timeout': data.llm_timeout,
        }

        # Criptografa credenciais se fornecidas
        if data.credentials:
            project_data['encrypted_credentials'] = encrypt_value(
                json.dumps(data.credentials)
            )

        # Criptografa chave de API do LLM se fornecida
        if data.llm_api_key:
            project_data['encrypted_llm_api_key'] = encrypt_value(data.llm_api_key)

        return project_data

    def _prepare_update_data(self, data: ProjectUpdate) -> dict:
        """
        Prepara os dados para atualizacao de projeto, criptografando campos sensiveis.

        Apenas campos com valores nao-None sao incluidos no dicionario.

        Args:
            data: Dados do schema de atualizacao.

        Returns:
            Dicionario com campos a atualizar.
        """
        update_data: dict = {}

        # Campos simples (inclui apenas os fornecidos)
        simple_fields = [
            'name', 'base_url', 'description', 'llm_provider',
            'llm_model', 'llm_temperature', 'llm_max_tokens',
            'llm_timeout', 'is_active',
        ]

        for field in simple_fields:
            value = getattr(data, field)
            if value is not None:
                update_data[field] = value

        # Criptografa credenciais se fornecidas
        if data.credentials is not None:
            update_data['encrypted_credentials'] = encrypt_value(
                json.dumps(data.credentials)
            )

        # Criptografa chave de API do LLM se fornecida
        if data.llm_api_key is not None:
            update_data['encrypted_llm_api_key'] = encrypt_value(data.llm_api_key)

        return update_data
