from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DeliveryResult:
    """
    Resultado de uma tentativa de entrega.

    Attributes:
        success: Se a entrega foi bem-sucedida.
        error_message: Mensagem de erro em caso de falha.
    """

    success: bool
    error_message: str | None = None


class DeliveryChannel(ABC):
    """
    Classe abstrata base para canais de entrega.

    Cada canal de entrega (email, webhook, etc.) deve implementar
    esta interface para ser utilizado pelo DeliveryService.
    """

    @abstractmethod
    def send(
        self,
        recipients: list[str],
        pdf_path: str | None,
        config: dict | None,
        execution_data: dict | None = None,
    ) -> DeliveryResult:
        """
        Envia o resultado da execucao atraves do canal configurado.

        Args:
            recipients: Lista de destinatarios.
            pdf_path: Caminho do arquivo PDF no storage (MinIO).
            config: Configuracoes especificas do canal (ex: assunto do email).
            execution_data: Dados adicionais da execucao para incluir na entrega.

        Returns:
            DeliveryResult indicando sucesso ou falha da entrega.
        """
        ...
