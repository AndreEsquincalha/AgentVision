import logging
from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.config import settings

logger = logging.getLogger(__name__)


class StorageClient:
    """
    Cliente para MinIO/S3 usando boto3.

    Fornece metodos para upload, download, geracao de URLs presigned
    e exclusao de arquivos no storage.
    """

    def __init__(self) -> None:
        """Inicializa o cliente boto3 com as configuracoes do MinIO."""
        self._client = boto3.client(
            's3',
            endpoint_url=f'{"https" if settings.minio_use_ssl else "http"}://{settings.minio_endpoint}',
            aws_access_key_id=settings.minio_access_key,
            aws_secret_access_key=settings.minio_secret_key,
            region_name='us-east-1',
        )
        self._bucket = settings.minio_bucket

    def ensure_bucket_exists(self) -> None:
        """
        Cria o bucket padrao se ele nao existir.

        O bucket e criado como privado por padrao (sem policy publica).
        Acesso a objetos e feito exclusivamente via presigned URLs.
        """
        try:
            self._client.head_bucket(Bucket=self._bucket)
            logger.info('Bucket "%s" ja existe.', self._bucket)
        except ClientError:
            try:
                self._client.create_bucket(Bucket=self._bucket)
                logger.info('Bucket "%s" criado com sucesso (acesso privado).', self._bucket)

                # Garante que o bucket nao possui policy publica.
                # Remover qualquer policy existente garante acesso privado.
                try:
                    self._client.delete_bucket_policy(Bucket=self._bucket)
                except ClientError:
                    # Nao ha policy para remover — bucket ja e privado
                    pass

            except ClientError as e:
                logger.error('Erro ao criar bucket "%s": %s', self._bucket, e)
                raise

    def upload_file(
        self,
        key: str,
        file_data: bytes,
        content_type: str = 'application/octet-stream',
        bucket: str | None = None,
    ) -> str:
        """
        Faz upload de um arquivo para o storage.

        Args:
            key: Caminho/nome do arquivo no bucket.
            file_data: Conteudo do arquivo em bytes.
            content_type: Tipo MIME do arquivo.
            bucket: Nome do bucket (usa padrao se nao informado).

        Returns:
            Caminho do arquivo no storage.
        """
        target_bucket = bucket or self._bucket
        try:
            self._client.put_object(
                Bucket=target_bucket,
                Key=key,
                Body=file_data,
                ContentType=content_type,
            )
            logger.info('Arquivo enviado: %s/%s', target_bucket, key)
            return key
        except ClientError as e:
            logger.error('Erro ao enviar arquivo %s: %s', key, e)
            raise

    def download_file(
        self,
        key: str,
        bucket: str | None = None,
    ) -> bytes:
        """
        Faz download de um arquivo do storage.

        Args:
            key: Caminho/nome do arquivo no bucket.
            bucket: Nome do bucket (usa padrao se nao informado).

        Returns:
            Conteudo do arquivo em bytes.
        """
        target_bucket = bucket or self._bucket
        try:
            response = self._client.get_object(
                Bucket=target_bucket,
                Key=key,
            )
            data: bytes = response['Body'].read()
            logger.info('Arquivo baixado: %s/%s', target_bucket, key)
            return data
        except ClientError as e:
            logger.error('Erro ao baixar arquivo %s: %s', key, e)
            raise

    def get_presigned_url(
        self,
        key: str,
        expiration: int = 3600,
        bucket: str | None = None,
    ) -> str:
        """
        Gera uma URL presigned para acesso temporario ao arquivo.

        Quando MINIO_PUBLIC_ENDPOINT esta configurado, substitui o endpoint
        interno (Docker) pelo endpoint publico na URL gerada, permitindo
        acesso pelo browser do usuario.

        Args:
            key: Caminho/nome do arquivo no bucket.
            expiration: Tempo de expiracao da URL em segundos (padrao: 1 hora).
            bucket: Nome do bucket (usa padrao se nao informado).

        Returns:
            URL presigned para acesso ao arquivo.
        """
        target_bucket = bucket or self._bucket
        try:
            url: str = self._client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': target_bucket,
                    'Key': key,
                },
                ExpiresIn=expiration,
            )

            # Substitui o endpoint interno pelo publico para que o browser
            # do usuario consiga acessar a URL (ex: minio:9000 -> localhost:9000)
            public_endpoint = settings.minio_public_endpoint
            if public_endpoint:
                internal_endpoint = settings.minio_endpoint
                url = url.replace(internal_endpoint, public_endpoint, 1)

            return url
        except ClientError as e:
            logger.error('Erro ao gerar URL presigned para %s: %s', key, e)
            raise

    def delete_file(
        self,
        key: str,
        bucket: str | None = None,
    ) -> None:
        """
        Exclui um arquivo do storage.

        Args:
            key: Caminho/nome do arquivo no bucket.
            bucket: Nome do bucket (usa padrao se nao informado).
        """
        target_bucket = bucket or self._bucket
        try:
            self._client.delete_object(
                Bucket=target_bucket,
                Key=key,
            )
            logger.info('Arquivo excluido: %s/%s', target_bucket, key)
        except ClientError as e:
            logger.error('Erro ao excluir arquivo %s: %s', key, e)
            raise

    def list_files(
        self,
        prefix: str = '',
        bucket: str | None = None,
    ) -> list[str]:
        """
        Lista arquivos no storage com um prefixo.

        Args:
            prefix: Prefixo para filtrar arquivos.
            bucket: Nome do bucket (usa padrao se nao informado).

        Returns:
            Lista de caminhos dos arquivos encontrados.
        """
        target_bucket = bucket or self._bucket
        try:
            response = self._client.list_objects_v2(
                Bucket=target_bucket,
                Prefix=prefix,
            )
            files: list[str] = []
            for obj in response.get('Contents', []):
                files.append(obj['Key'])
            return files
        except ClientError as e:
            logger.error('Erro ao listar arquivos com prefixo %s: %s', prefix, e)
            raise
