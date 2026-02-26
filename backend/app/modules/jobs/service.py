import uuid
from datetime import datetime

from croniter import croniter

from app.modules.delivery.repository import DeliveryRepository
from app.modules.jobs.models import Job
from app.modules.jobs.repository import JobRepository
from app.modules.jobs.schemas import (
    DeliveryConfigInline,
    DryRunResponse,
    JobCreate,
    JobListResponse,
    JobResponse,
    JobToggle,
    JobUpdate,
)
from app.modules.projects.repository import ProjectRepository
from app.shared.exceptions import BadRequestException, NotFoundException
from app.shared.schemas import PaginatedResponse
from app.shared.utils import encrypt_dict, utc_now


class JobService:
    """
    Servico de jobs.

    Contem a logica de negocio para operacoes CRUD de jobs,
    incluindo validacao de projeto, calculo de proxima execucao
    e criacao de configuracoes de entrega associadas.
    """

    def __init__(
        self,
        repository: JobRepository,
        project_repository: ProjectRepository,
        delivery_repository: DeliveryRepository,
    ) -> None:
        """Inicializa o servico com os repositorios necessarios."""
        self._repository = repository
        self._project_repository = project_repository
        self._delivery_repository = delivery_repository

    def list_jobs(
        self,
        page: int = 1,
        per_page: int = 20,
        project_id: uuid.UUID | None = None,
        is_active: bool | None = None,
        search: str | None = None,
    ) -> PaginatedResponse[JobResponse]:
        """
        Lista jobs com paginacao e filtros.

        Args:
            page: Numero da pagina.
            per_page: Itens por pagina.
            project_id: Filtro por projeto.
            is_active: Filtro por status ativo/inativo.
            search: Termo de busca (nome).

        Returns:
            Resposta paginada com lista de jobs.
        """
        jobs, total = self._repository.get_all(
            page=page,
            per_page=per_page,
            project_id=project_id,
            is_active=is_active,
            search=search,
        )

        job_responses = [
            JobResponse.from_model(
                job,
                next_execution=self.get_next_execution_time(job.cron_expression)
                if job.is_active else None,
            )
            for job in jobs
        ]

        return PaginatedResponse[JobResponse].create(
            items=job_responses,
            total=total,
            page=page,
            per_page=per_page,
        )

    def get_job(self, job_id: uuid.UUID) -> JobResponse:
        """
        Busca um job pelo ID.

        Args:
            job_id: ID do job.

        Returns:
            Dados do job.

        Raises:
            NotFoundException: Se o job nao for encontrado.
        """
        job = self._repository.get_by_id(job_id)
        if not job:
            raise NotFoundException('Job nao encontrado')

        next_execution = (
            self.get_next_execution_time(job.cron_expression)
            if job.is_active else None
        )

        return JobResponse.from_model(job, next_execution=next_execution)

    def create_job(self, data: JobCreate) -> JobResponse:
        """
        Cria um novo job com suas configuracoes de entrega.

        Valida que o projeto existe e esta ativo antes de criar.
        Se delivery_configs forem fornecidas, cria-as em uma unica transacao.

        Args:
            data: Dados do job a ser criado.

        Returns:
            Dados do job criado.

        Raises:
            NotFoundException: Se o projeto nao for encontrado.
            BadRequestException: Se o projeto estiver inativo.
        """
        # Valida que o projeto existe e esta ativo
        project = self._project_repository.get_by_id(data.project_id)
        if not project:
            raise NotFoundException('Projeto nao encontrado')
        if not project.is_active:
            raise BadRequestException(
                'Nao e possivel criar job para um projeto inativo'
            )

        # Prepara dados do job (sem delivery_configs)
        job_data: dict = {
            'project_id': data.project_id,
            'name': data.name,
            'cron_expression': data.cron_expression,
            'agent_prompt': data.agent_prompt,
            'prompt_template_id': data.prompt_template_id,
            'execution_params': data.execution_params,
            'priority': data.priority.value if data.priority else 'normal',
            'notify_on_failure': data.notify_on_failure,
        }

        # Cria o job
        job = self._repository.create(job_data)

        # Cria configuracoes de entrega associadas, se fornecidas
        if data.delivery_configs:
            self._create_delivery_configs(job.id, data.delivery_configs)
            # Recarrega o job para incluir os delivery_configs no relacionamento
            job = self._repository.get_by_id(job.id)

        next_execution = self.get_next_execution_time(job.cron_expression)
        return JobResponse.from_model(job, next_execution=next_execution)

    def update_job(
        self,
        job_id: uuid.UUID,
        data: JobUpdate,
    ) -> JobResponse:
        """
        Atualiza um job existente.

        Args:
            job_id: ID do job a ser atualizado.
            data: Dados a serem atualizados.

        Returns:
            Dados do job atualizado.

        Raises:
            NotFoundException: Se o job nao for encontrado.
        """
        existing = self._repository.get_by_id(job_id)
        if not existing:
            raise NotFoundException('Job nao encontrado')

        update_data = self._prepare_update_data(data)

        # Se nao ha campos para atualizar, retorna o job atual
        if not update_data:
            next_execution = (
                self.get_next_execution_time(existing.cron_expression)
                if existing.is_active else None
            )
            return JobResponse.from_model(existing, next_execution=next_execution)

        job = self._repository.update(job_id, update_data)
        if not job:
            raise NotFoundException('Job nao encontrado')

        next_execution = (
            self.get_next_execution_time(job.cron_expression)
            if job.is_active else None
        )
        return JobResponse.from_model(job, next_execution=next_execution)

    def delete_job(self, job_id: uuid.UUID) -> None:
        """
        Realiza soft delete de um job.

        Args:
            job_id: ID do job a ser excluido.

        Raises:
            NotFoundException: Se o job nao for encontrado.
        """
        success = self._repository.soft_delete(job_id)
        if not success:
            raise NotFoundException('Job nao encontrado')

    def toggle_active(self, job_id: uuid.UUID, data: JobToggle) -> JobResponse:
        """
        Ativa ou desativa um job.

        Args:
            job_id: ID do job.
            data: Dados com o novo status.

        Returns:
            Dados do job atualizado.

        Raises:
            NotFoundException: Se o job nao for encontrado.
        """
        existing = self._repository.get_by_id(job_id)
        if not existing:
            raise NotFoundException('Job nao encontrado')

        job = self._repository.update(job_id, {'is_active': data.is_active})
        if not job:
            raise NotFoundException('Job nao encontrado')

        next_execution = (
            self.get_next_execution_time(job.cron_expression)
            if job.is_active else None
        )
        return JobResponse.from_model(job, next_execution=next_execution)

    def trigger_dry_run(self, job_id: uuid.UUID) -> DryRunResponse:
        """
        Inicia um dry run para um job.

        Despacha a task Celery execute_job com is_dry_run=True.
        O dry run executa todo o fluxo (navegacao, screenshots, analise, PDF)
        porem nao realiza a etapa de entrega.

        Args:
            job_id: ID do job para executar o dry run.

        Returns:
            Dados do dry run iniciado.

        Raises:
            NotFoundException: Se o job nao for encontrado.
            BadRequestException: Se o job estiver inativo.
        """
        job = self._repository.get_by_id(job_id)
        if not job:
            raise NotFoundException('Job nao encontrado')

        if not job.is_active:
            raise BadRequestException(
                'Nao e possivel executar dry run de um job inativo'
            )

        # Despacha a task Celery para execucao assincrona
        # Roteia para queue 'priority' se job de alta prioridade
        from app.modules.jobs.tasks import execute_job
        target_queue = 'priority' if job.priority == 'high' else 'execution'
        execute_job.apply_async(
            args=[str(job.id), True],
            queue=target_queue,
        )

        return DryRunResponse(
            job_id=job.id,
            job_name=job.name,
            status='pending',
            is_dry_run=True,
            message='Dry run iniciado com sucesso. A execucao sera processada pelo worker.',
        )

    @staticmethod
    def get_next_execution_time(cron_expression: str) -> datetime | None:
        """
        Calcula a proxima data/hora de execucao com base na expressao cron.

        Args:
            cron_expression: Expressao cron valida.

        Returns:
            Proxima data/hora de execucao ou None se invalida.
        """
        try:
            now = utc_now()
            cron = croniter(cron_expression, now)
            next_time: datetime = cron.get_next(datetime)
            return next_time
        except (ValueError, KeyError):
            return None

    # -------------------------------------------------------------------------
    # Metodos auxiliares privados
    # -------------------------------------------------------------------------

    def _create_delivery_configs(
        self,
        job_id: uuid.UUID,
        configs: list[DeliveryConfigInline],
    ) -> None:
        """
        Cria configuracoes de entrega associadas a um job.

        Args:
            job_id: ID do job.
            configs: Lista de configuracoes de entrega inline.
        """
        for config in configs:
            encrypted_config = (
                encrypt_dict(config.channel_config) if config.channel_config else None
            )
            config_data: dict = {
                'job_id': job_id,
                'channel_type': config.channel_type,
                'recipients': config.recipients,
                'channel_config': encrypted_config,
                'is_active': config.is_active,
            }
            self._delivery_repository.create_config(config_data)

    def _prepare_update_data(self, data: JobUpdate) -> dict:
        """
        Prepara os dados para atualizacao de job.

        Apenas campos com valores nao-None sao incluidos no dicionario.

        Args:
            data: Dados do schema de atualizacao.

        Returns:
            Dicionario com campos a atualizar.
        """
        update_data: dict = {}

        fields = [
            'name', 'cron_expression', 'agent_prompt',
            'prompt_template_id', 'execution_params', 'priority',
            'notify_on_failure', 'is_active',
        ]

        for field in fields:
            value = getattr(data, field)
            if value is not None:
                update_data[field] = value

        return update_data
