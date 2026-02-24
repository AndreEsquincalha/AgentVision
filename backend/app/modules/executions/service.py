import logging
import uuid

from app.modules.delivery.service import DeliveryService
from app.modules.executions.models import Execution
from app.modules.executions.repository import ExecutionRepository
from app.modules.executions.schemas import (
    ExecutionDetailResponse,
    ExecutionFilter,
    ExecutionListItemResponse,
    ExecutionListResponse,
    PdfUrlResponse,
    ScreenshotUrlResponse,
)
from app.shared.exceptions import BadRequestException, NotFoundException
from app.shared.schemas import PaginatedResponse
from app.shared.storage import StorageClient

logger = logging.getLogger(__name__)


class ExecutionService:
    """
    Servico de execucoes.

    Contem a logica de negocio para consulta de execucoes,
    geracao de URLs presigned para artefatos (screenshots, PDF)
    e criacao de novas execucoes.
    """

    def __init__(
        self,
        repository: ExecutionRepository,
        storage_client: StorageClient,
        delivery_service: DeliveryService,
    ) -> None:
        """Inicializa o servico com o repositorio e cliente de storage."""
        self._repository = repository
        self._storage = storage_client
        self._delivery_service = delivery_service

    def list_executions(
        self,
        page: int = 1,
        per_page: int = 20,
        filters: ExecutionFilter | None = None,
    ) -> ExecutionListResponse:
        """
        Lista execucoes com paginacao e filtros.

        Args:
            page: Numero da pagina.
            per_page: Itens por pagina.
            filters: Filtros opcionais (job_id, project_id, status, etc.).

        Returns:
            Resposta paginada com lista de execucoes.
        """
        # Extrai filtros se fornecidos
        job_id = filters.job_id if filters else None
        project_id = filters.project_id if filters else None
        status = filters.status if filters else None
        date_from = filters.date_from if filters else None
        date_to = filters.date_to if filters else None
        is_dry_run = filters.is_dry_run if filters else None

        executions, total = self._repository.get_all(
            page=page,
            per_page=per_page,
            job_id=job_id,
            project_id=project_id,
            status=status,
            date_from=date_from,
            date_to=date_to,
            is_dry_run=is_dry_run,
        )

        execution_responses = [
            ExecutionListItemResponse.from_model(execution)
            for execution in executions
        ]

        return PaginatedResponse[ExecutionListItemResponse].create(
            items=execution_responses,
            total=total,
            page=page,
            per_page=per_page,
        )

    def get_execution(self, execution_id: uuid.UUID) -> ExecutionDetailResponse:
        """
        Busca uma execucao pelo ID com todos os detalhes.

        Args:
            execution_id: ID da execucao.

        Returns:
            Dados completos da execucao incluindo logs de entrega.

        Raises:
            NotFoundException: Se a execucao nao for encontrada.
        """
        execution = self._repository.get_by_id(execution_id)
        if not execution:
            raise NotFoundException('Execucao nao encontrada')

        return ExecutionDetailResponse.from_model(execution)

    def get_screenshot_urls(
        self,
        execution_id: uuid.UUID,
    ) -> ScreenshotUrlResponse:
        """
        Gera URLs presigned para os screenshots de uma execucao.

        Busca a execucao, verifica se possui screenshots_path,
        lista os arquivos no MinIO e gera URLs temporarias.

        Args:
            execution_id: ID da execucao.

        Returns:
            Lista de URLs presigned para os screenshots.

        Raises:
            NotFoundException: Se a execucao nao for encontrada.
            BadRequestException: Se a execucao nao possui screenshots.
        """
        execution = self._repository.get_by_id(execution_id)
        if not execution:
            raise NotFoundException('Execucao nao encontrada')

        if not execution.screenshots_path:
            raise BadRequestException(
                'Esta execucao nao possui screenshots'
            )

        try:
            # Lista arquivos no storage no path dos screenshots
            files = self._storage.list_files(prefix=execution.screenshots_path)

            # Filtra apenas arquivos de imagem
            image_extensions = ('.png', '.jpg', '.jpeg', '.webp', '.gif')
            image_files = [
                f for f in files
                if f.lower().endswith(image_extensions)
            ]

            # Gera URLs presigned para cada screenshot
            urls: list[str] = [
                self._storage.get_presigned_url(key=f)
                for f in image_files
            ]

            return ScreenshotUrlResponse(
                execution_id=execution_id,
                urls=urls,
            )
        except Exception as e:
            logger.error(
                'Erro ao gerar URLs de screenshots para execucao %s: %s',
                execution_id,
                str(e),
            )
            raise BadRequestException(
                f'Erro ao acessar screenshots: {str(e)}'
            )

    def get_pdf_url(self, execution_id: uuid.UUID) -> PdfUrlResponse:
        """
        Gera URL presigned para o PDF de uma execucao.

        Args:
            execution_id: ID da execucao.

        Returns:
            URL presigned para o PDF.

        Raises:
            NotFoundException: Se a execucao nao for encontrada.
            BadRequestException: Se a execucao nao possui PDF.
        """
        execution = self._repository.get_by_id(execution_id)
        if not execution:
            raise NotFoundException('Execucao nao encontrada')

        if not execution.pdf_path:
            raise BadRequestException(
                'Esta execucao nao possui PDF gerado'
            )

        try:
            url = self._storage.get_presigned_url(key=execution.pdf_path)

            return PdfUrlResponse(
                execution_id=execution_id,
                url=url,
            )
        except Exception as e:
            logger.error(
                'Erro ao gerar URL do PDF para execucao %s: %s',
                execution_id,
                str(e),
            )
            raise BadRequestException(
                f'Erro ao acessar PDF: {str(e)}'
            )

    def create_execution(
        self,
        job_id: uuid.UUID,
        is_dry_run: bool = False,
    ) -> Execution:
        """
        Cria uma nova execucao para um job.

        Args:
            job_id: ID do job a ser executado.
            is_dry_run: Se verdadeiro, a execucao e de teste.

        Returns:
            Execucao criada com status 'pending'.
        """
        execution_data: dict = {
            'job_id': job_id,
            'status': 'pending',
            'is_dry_run': is_dry_run,
        }

        execution = self._repository.create(execution_data)
        return execution

    def delete_execution(self, execution_id: uuid.UUID) -> None:
        """
        Exclui uma execucao e seus artefatos associados.

        Remove screenshots e PDF do MinIO (se existirem),
        deleta os delivery logs vinculados e a execucao do banco.

        Args:
            execution_id: ID da execucao a ser excluida.

        Raises:
            NotFoundException: Se a execucao nao for encontrada.
        """
        execution = self._repository.get_by_id(execution_id)
        if not execution:
            raise NotFoundException('Execucao nao encontrada')

        # Remove screenshots do MinIO (se existirem)
        if execution.screenshots_path:
            try:
                files = self._storage.list_files(
                    prefix=execution.screenshots_path,
                )
                for file_key in files:
                    self._storage.delete_file(key=file_key)
                logger.info(
                    'Screenshots removidos do storage para execucao %s',
                    execution_id,
                )
            except Exception as e:
                logger.warning(
                    'Erro ao remover screenshots da execucao %s: %s',
                    execution_id,
                    str(e),
                )

        # Remove PDF do MinIO (se existir)
        if execution.pdf_path:
            try:
                self._storage.delete_file(key=execution.pdf_path)
                logger.info(
                    'PDF removido do storage para execucao %s',
                    execution_id,
                )
            except Exception as e:
                logger.warning(
                    'Erro ao remover PDF da execucao %s: %s',
                    execution_id,
                    str(e),
                )

        # Deleta a execucao e delivery logs do banco
        self._repository.delete(execution_id)
        logger.info('Execucao %s excluida com sucesso', execution_id)

    def retry_delivery(
        self,
        execution_id: uuid.UUID,
        delivery_log_id: uuid.UUID,
    ) -> 'DeliveryLogResponse':
        """
        Retenta uma entrega que falhou para uma execucao.

        Delega a logica de retry para o DeliveryService.

        Args:
            execution_id: ID da execucao (para validacao).
            delivery_log_id: ID do log de entrega a ser retentado.

        Returns:
            Log de entrega atualizado.

        Raises:
            NotFoundException: Se a execucao nao for encontrada.
        """
        from app.modules.delivery.schemas import DeliveryLogResponse

        # Valida que a execucao existe
        execution = self._repository.get_by_id(execution_id)
        if not execution:
            raise NotFoundException('Execucao nao encontrada')

        # Delega ao servico de entregas
        return self._delivery_service.retry_delivery(delivery_log_id)
