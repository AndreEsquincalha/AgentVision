import logging

from app.shared.storage import StorageClient

logger = logging.getLogger(__name__)


class ScreenshotManager:
    """
    Gerenciador de screenshots para execucoes de agentes.

    Responsavel por salvar, listar e gerar URLs de acesso
    para screenshots armazenados no MinIO/S3.
    """

    def __init__(self, storage_client: StorageClient) -> None:
        """
        Inicializa o gerenciador de screenshots.

        Args:
            storage_client: Cliente de storage (MinIO/S3) para operacoes de arquivo.
        """
        self._storage = storage_client

    def save_screenshot(
        self,
        image_bytes: bytes,
        execution_id: str,
        index: int,
    ) -> str:
        """
        Salva um screenshot no storage.

        Args:
            image_bytes: Dados da imagem em bytes (PNG).
            execution_id: ID da execucao associada.
            index: Indice sequencial do screenshot (usado no nome do arquivo).

        Returns:
            Caminho completo do arquivo no storage (ex: screenshots/{execution_id}/screenshot_000.png).
        """
        # Garante que o bucket existe antes do upload
        self._storage.ensure_bucket_exists()

        key = f'screenshots/{execution_id}/screenshot_{index:03d}.png'

        logger.info(
            'Salvando screenshot %d para execucao %s: %s',
            index,
            execution_id,
            key,
        )

        self._storage.upload_file(
            key=key,
            file_data=image_bytes,
            content_type='image/png',
        )

        logger.info('Screenshot salvo com sucesso: %s', key)
        return key

    def save_screenshots(
        self,
        screenshots: list[bytes],
        execution_id: str,
    ) -> list[str]:
        """
        Salva multiplos screenshots no storage.

        Metodo de conveniencia que itera sobre a lista de screenshots
        e salva cada um com indice sequencial.

        Args:
            screenshots: Lista de imagens em bytes (PNG).
            execution_id: ID da execucao associada.

        Returns:
            Lista de caminhos dos arquivos salvos no storage.
        """
        if not screenshots:
            logger.warning(
                'Nenhum screenshot para salvar na execucao %s',
                execution_id,
            )
            return []

        logger.info(
            'Salvando %d screenshots para execucao %s',
            len(screenshots),
            execution_id,
        )

        paths: list[str] = []
        for index, image_bytes in enumerate(screenshots):
            path = self.save_screenshot(
                image_bytes=image_bytes,
                execution_id=execution_id,
                index=index,
            )
            paths.append(path)

        logger.info(
            'Todos os %d screenshots salvos para execucao %s',
            len(paths),
            execution_id,
        )
        return paths

    def get_screenshot_urls(
        self,
        execution_id: str,
        expiration: int = 3600,
    ) -> list[str]:
        """
        Gera URLs presigned para todos os screenshots de uma execucao.

        Args:
            execution_id: ID da execucao.
            expiration: Tempo de expiracao das URLs em segundos (padrao: 1 hora).

        Returns:
            Lista de URLs presigned para acesso temporario aos screenshots.
        """
        prefix = f'screenshots/{execution_id}/'

        logger.info(
            'Listando screenshots para execucao %s (prefixo: %s)',
            execution_id,
            prefix,
        )

        # Lista arquivos no storage com o prefixo da execucao
        files = self._storage.list_files(prefix=prefix)

        # Filtra apenas arquivos de imagem
        image_extensions = ('.png', '.jpg', '.jpeg', '.gif', '.webp')
        image_files = [
            f for f in files
            if f.lower().endswith(image_extensions)
        ]

        # Ordena pelo nome para manter a ordem sequencial
        image_files.sort()

        # Gera URLs presigned para cada arquivo
        urls: list[str] = []
        for file_key in image_files:
            url = self._storage.get_presigned_url(
                key=file_key,
                expiration=expiration,
            )
            urls.append(url)

        logger.info(
            'Geradas %d URLs de screenshots para execucao %s',
            len(urls),
            execution_id,
        )

        return urls
