import logging
import os
import shutil
from datetime import datetime

from app.modules.delivery.base_channel import DeliveryChannel, DeliveryResult
from app.shared.storage import StorageClient

logger = logging.getLogger(__name__)


class StorageChannel(DeliveryChannel):
    """
    Canal de entrega que salva o PDF em disco local ou bucket S3 externo.

    Util para integracao com outros sistemas via filesystem ou para
    manter copias dos relatorios em locais especificos.

    O path_template suporta variaveis de substituicao:
        {project}  - Nome do projeto
        {job}      - Nome do job
        {date}     - Data da execucao (YYYY-MM-DD)
        {datetime} - Data e hora (YYYY-MM-DD_HH-MM-SS)
        {execution_id} - ID da execucao
        {year}     - Ano (YYYY)
        {month}    - Mes (MM)
    """

    def __init__(
        self,
        storage_type: str = 'local',
        path_template: str = '{project}/{job}/{date}/report.pdf',
        base_path: str = '/data/reports',
        s3_bucket: str | None = None,
        s3_endpoint: str | None = None,
        s3_access_key: str | None = None,
        s3_secret_key: str | None = None,
    ) -> None:
        """
        Inicializa o canal de armazenamento.

        Args:
            storage_type: Tipo de armazenamento ('local' ou 's3').
            path_template: Template do caminho com variaveis.
            base_path: Caminho base para armazenamento local.
            s3_bucket: Nome do bucket S3 externo (para tipo 's3').
            s3_endpoint: Endpoint S3 (para tipo 's3').
            s3_access_key: Chave de acesso S3.
            s3_secret_key: Chave secreta S3.
        """
        self._storage_type = storage_type
        self._path_template = path_template
        self._base_path = base_path
        self._s3_bucket = s3_bucket
        self._s3_endpoint = s3_endpoint
        self._s3_access_key = s3_access_key
        self._s3_secret_key = s3_secret_key

    def send(
        self,
        recipients: list[str],
        pdf_path: str | None,
        config: dict | None,
        execution_data: dict | None = None,
    ) -> DeliveryResult:
        """
        Salva o PDF no destino configurado.

        Args:
            recipients: Nao utilizado neste canal (ignorado).
            pdf_path: Caminho do PDF no storage MinIO interno.
            config: Configuracoes adicionais.
            execution_data: Dados da execucao para resolucao do template.

        Returns:
            DeliveryResult indicando sucesso ou falha.
        """
        if not pdf_path:
            return DeliveryResult(
                success=False,
                error_message='Nenhum PDF disponivel para salvar',
            )

        try:
            # Resolve o path template
            target_path = self._resolve_path_template(execution_data)

            # Faz download do PDF do MinIO interno
            storage = StorageClient()
            pdf_bytes = storage.download_file(pdf_path)

            if self._storage_type == 's3':
                return self._save_to_s3(target_path, pdf_bytes)
            else:
                return self._save_to_local(target_path, pdf_bytes)

        except Exception as e:
            error_msg = f'Erro ao salvar PDF no storage: {str(e)[:300]}'
            logger.error(error_msg)
            return DeliveryResult(success=False, error_message=error_msg)

    def _resolve_path_template(
        self,
        execution_data: dict | None,
    ) -> str:
        """Resolve variaveis no path template."""
        data = execution_data or {}
        now = datetime.utcnow()

        # Sanitiza nomes para uso em paths (remove caracteres especiais)
        project_name = self._sanitize_path_component(
            data.get('project_name', 'unknown_project')
        )
        job_name = self._sanitize_path_component(
            data.get('job_name', 'unknown_job')
        )

        variables = {
            'project': project_name,
            'job': job_name,
            'date': now.strftime('%Y-%m-%d'),
            'datetime': now.strftime('%Y-%m-%d_%H-%M-%S'),
            'execution_id': data.get('execution_id', 'unknown'),
            'year': now.strftime('%Y'),
            'month': now.strftime('%m'),
        }

        resolved = self._path_template
        for key, value in variables.items():
            resolved = resolved.replace(f'{{{key}}}', value)

        return resolved

    @staticmethod
    def _sanitize_path_component(name: str) -> str:
        """Remove caracteres especiais de um componente de path."""
        # Substitui caracteres nao alfanumericos por underscore
        sanitized = ''
        for char in name:
            if char.isalnum() or char in ('-', '_', '.'):
                sanitized += char
            else:
                sanitized += '_'
        return sanitized.strip('_') or 'unnamed'

    def _save_to_local(self, target_path: str, pdf_bytes: bytes) -> DeliveryResult:
        """Salva PDF em disco local."""
        full_path = os.path.join(self._base_path, target_path)

        # Cria diretorios intermediarios
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        with open(full_path, 'wb') as f:
            f.write(pdf_bytes)

        logger.info('PDF salvo em disco local: %s', full_path)
        return DeliveryResult(success=True)

    def _save_to_s3(self, target_path: str, pdf_bytes: bytes) -> DeliveryResult:
        """Salva PDF em bucket S3 externo."""
        if not self._s3_bucket:
            return DeliveryResult(
                success=False,
                error_message='Bucket S3 nao configurado',
            )

        try:
            import boto3

            # Cria cliente S3 para o bucket externo
            client_kwargs: dict = {
                'aws_access_key_id': self._s3_access_key,
                'aws_secret_access_key': self._s3_secret_key,
                'region_name': 'us-east-1',
            }
            if self._s3_endpoint:
                protocol = 'https' if 'https' in self._s3_endpoint else 'http'
                endpoint = self._s3_endpoint
                if not endpoint.startswith('http'):
                    endpoint = f'{protocol}://{endpoint}'
                client_kwargs['endpoint_url'] = endpoint

            s3_client = boto3.client('s3', **client_kwargs)

            s3_client.put_object(
                Bucket=self._s3_bucket,
                Key=target_path,
                Body=pdf_bytes,
                ContentType='application/pdf',
            )

            logger.info(
                'PDF salvo no S3: %s/%s',
                self._s3_bucket, target_path,
            )
            return DeliveryResult(success=True)

        except Exception as e:
            error_msg = f'Erro ao salvar no S3: {str(e)[:300]}'
            logger.error(error_msg)
            return DeliveryResult(success=False, error_message=error_msg)
