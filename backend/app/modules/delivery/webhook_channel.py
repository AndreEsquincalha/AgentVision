import json
import logging
import time
from urllib.parse import urlparse

import requests

from app.modules.delivery.base_channel import DeliveryChannel, DeliveryResult

logger = logging.getLogger(__name__)

# Backoff delays para retry (em segundos)
_RETRY_DELAYS = (1, 5, 15)

# Timeout padrao para requests HTTP (connect, read)
_DEFAULT_TIMEOUT = (10, 30)


class WebhookChannel(DeliveryChannel):
    """
    Canal de entrega via webhook HTTP.

    Envia um POST (ou PUT) com payload JSON contendo dados da execucao
    e link para o PDF. Suporta autenticacao Bearer e Basic,
    headers customizados e retry com backoff exponencial.
    """

    def __init__(
        self,
        url: str,
        method: str = 'POST',
        headers: dict | None = None,
        auth_type: str | None = None,
        auth_token: str | None = None,
        auth_user: str | None = None,
        auth_password: str | None = None,
        verify_ssl: bool = True,
    ) -> None:
        """
        Inicializa o canal webhook.

        Args:
            url: URL de destino do webhook.
            method: Metodo HTTP (POST ou PUT).
            headers: Headers customizados adicionais.
            auth_type: Tipo de autenticacao (bearer, basic ou None).
            auth_token: Token para autenticacao Bearer.
            auth_user: Usuario para autenticacao Basic.
            auth_password: Senha para autenticacao Basic.
            verify_ssl: Se deve verificar certificado SSL.
        """
        self._url = url
        self._method = method.upper()
        self._custom_headers = headers or {}
        self._auth_type = auth_type
        self._auth_token = auth_token
        self._auth_user = auth_user
        self._auth_password = auth_password
        self._verify_ssl = verify_ssl

    def send(
        self,
        recipients: list[str],
        pdf_path: str | None,
        config: dict | None,
        execution_data: dict | None = None,
    ) -> DeliveryResult:
        """
        Envia dados da execucao via webhook com retry automatico.

        Args:
            recipients: Lista de URLs de webhook (usa self._url se vazio).
            pdf_path: Caminho do PDF no storage (incluido no payload).
            config: Configuracoes adicionais do canal.
            execution_data: Dados da execucao para o payload.

        Returns:
            DeliveryResult indicando sucesso ou falha.
        """
        # Monta payload
        payload = self._build_payload(pdf_path, execution_data)

        # Monta headers
        headers = self._build_headers()

        # Auth
        auth = self._build_auth()

        # Envia para cada URL (recipients como URLs ou URL principal)
        urls = recipients if recipients else [self._url]
        errors: list[str] = []

        for target_url in urls:
            result = self._send_with_retry(target_url, payload, headers, auth)
            if not result.success:
                errors.append(f'{target_url}: {result.error_message}')

        if errors:
            return DeliveryResult(
                success=False,
                error_message='; '.join(errors),
            )

        return DeliveryResult(success=True)

    def _build_payload(
        self,
        pdf_path: str | None,
        execution_data: dict | None,
    ) -> dict:
        """Constroi o payload JSON do webhook."""
        payload: dict = {
            'event': 'execution_completed',
            'pdf_path': pdf_path,
        }
        if execution_data:
            payload['execution'] = execution_data
        return payload

    def _build_headers(self) -> dict:
        """Constroi os headers HTTP incluindo customizados."""
        headers = {
            'Content-Type': 'application/json',
            'User-Agent': 'AgentVision-Webhook/1.0',
        }
        headers.update(self._custom_headers)
        return headers

    def _build_auth(self) -> tuple | None:
        """Constroi autenticacao para requests."""
        if self._auth_type == 'basic' and self._auth_user:
            return (self._auth_user, self._auth_password or '')
        return None

    def _send_with_retry(
        self,
        url: str,
        payload: dict,
        headers: dict,
        auth: tuple | None,
    ) -> DeliveryResult:
        """
        Envia request HTTP com retry e backoff.

        Tenta ate 3 vezes com delays de 1s, 5s, 15s entre tentativas.
        """
        # Adiciona Bearer token ao header se configurado
        if self._auth_type == 'bearer' and self._auth_token:
            headers = {**headers, 'Authorization': f'Bearer {self._auth_token}'}

        last_error = ''
        max_attempts = len(_RETRY_DELAYS) + 1  # 1 tentativa inicial + 3 retries

        for attempt in range(max_attempts):
            try:
                if self._method == 'PUT':
                    response = requests.put(
                        url,
                        json=payload,
                        headers=headers,
                        auth=auth,
                        timeout=_DEFAULT_TIMEOUT,
                        verify=self._verify_ssl,
                    )
                else:
                    response = requests.post(
                        url,
                        json=payload,
                        headers=headers,
                        auth=auth,
                        timeout=_DEFAULT_TIMEOUT,
                        verify=self._verify_ssl,
                    )

                # Sucesso: 2xx
                if 200 <= response.status_code < 300:
                    logger.info(
                        'Webhook enviado com sucesso para %s (status=%d, tentativa=%d)',
                        url, response.status_code, attempt + 1,
                    )
                    return DeliveryResult(success=True)

                # Erro do servidor (5xx) — retry
                if response.status_code >= 500:
                    last_error = (
                        f'HTTP {response.status_code}: {response.text[:200]}'
                    )
                    logger.warning(
                        'Webhook falhou para %s (status=%d, tentativa=%d): %s',
                        url, response.status_code, attempt + 1, last_error,
                    )
                else:
                    # Erro do cliente (4xx) — nao faz retry
                    error_msg = (
                        f'HTTP {response.status_code}: {response.text[:200]}'
                    )
                    logger.error(
                        'Webhook rejeitado por %s (status=%d): %s',
                        url, response.status_code, error_msg,
                    )
                    return DeliveryResult(success=False, error_message=error_msg)

            except requests.exceptions.Timeout:
                last_error = f'Timeout ao conectar com {url}'
                logger.warning(
                    'Webhook timeout para %s (tentativa=%d)',
                    url, attempt + 1,
                )
            except requests.exceptions.ConnectionError as e:
                last_error = f'Erro de conexao com {url}: {str(e)[:200]}'
                logger.warning(
                    'Webhook erro de conexao para %s (tentativa=%d): %s',
                    url, attempt + 1, str(e)[:200],
                )
            except Exception as e:
                last_error = f'Erro inesperado ao enviar webhook para {url}: {str(e)[:200]}'
                logger.error(last_error)
                return DeliveryResult(success=False, error_message=last_error)

            # Backoff antes do proximo retry
            if attempt < len(_RETRY_DELAYS):
                delay = _RETRY_DELAYS[attempt]
                logger.info(
                    'Webhook retry em %ds para %s (tentativa %d/%d)',
                    delay, url, attempt + 2, max_attempts,
                )
                time.sleep(delay)

        return DeliveryResult(
            success=False,
            error_message=f'Falha apos {max_attempts} tentativas: {last_error}',
        )


def validate_webhook_url(url: str, require_https: bool = False) -> str | None:
    """
    Valida uma URL de webhook.

    Args:
        url: URL a validar.
        require_https: Se True, exige HTTPS.

    Returns:
        None se valida, mensagem de erro se invalida.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return 'URL invalida'

    if parsed.scheme not in ('http', 'https'):
        return 'URL deve usar protocolo HTTP ou HTTPS'

    if not parsed.netloc:
        return 'URL deve conter um host valido'

    if require_https and parsed.scheme != 'https':
        return 'URL deve usar HTTPS em ambiente de producao'

    return None
