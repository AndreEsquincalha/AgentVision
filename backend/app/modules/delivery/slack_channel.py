import logging

import requests

from app.modules.delivery.base_channel import DeliveryChannel, DeliveryResult

logger = logging.getLogger(__name__)

# Timeout para requests ao Slack
_SLACK_TIMEOUT = (10, 30)


class SlackChannel(DeliveryChannel):
    """
    Canal de entrega via Slack Incoming Webhook.

    Envia mensagens formatadas com Block Kit contendo titulo,
    sumario executivo, link para PDF e status badges.
    """

    def __init__(
        self,
        webhook_url: str,
        channel: str | None = None,
        mention_on_failure: bool = True,
        username: str = 'AgentVision',
        icon_emoji: str = ':robot_face:',
    ) -> None:
        """
        Inicializa o canal Slack.

        Args:
            webhook_url: URL do Incoming Webhook do Slack.
            channel: Canal de destino (opcional, usa default do webhook).
            mention_on_failure: Se True, menciona @here em caso de falha.
            username: Nome exibido no Slack.
            icon_emoji: Emoji do bot.
        """
        self._webhook_url = webhook_url
        self._channel = channel
        self._mention_on_failure = mention_on_failure
        self._username = username
        self._icon_emoji = icon_emoji

    def send(
        self,
        recipients: list[str],
        pdf_path: str | None,
        config: dict | None,
        execution_data: dict | None = None,
    ) -> DeliveryResult:
        """
        Envia mensagem formatada para o Slack.

        Args:
            recipients: Lista de canais adicionais (opcional).
            pdf_path: Caminho do PDF no storage.
            config: Configuracoes adicionais do canal.
            execution_data: Dados da execucao.

        Returns:
            DeliveryResult indicando sucesso ou falha.
        """
        try:
            # Extrai dados da execucao
            data = execution_data or {}
            job_name = data.get('job_name', 'N/A')
            project_name = data.get('project_name', 'N/A')
            execution_id = data.get('execution_id', 'N/A')
            started_at = data.get('started_at', 'N/A')
            summary = data.get('analysis_text', '') or data.get('summary', '')
            status = data.get('status', 'success')
            base_url = data.get('base_url', '')

            # Verifica se e notificacao de falha
            is_failure = status in ('failed', 'error')

            # Monta os blocos Slack Block Kit
            blocks = self._build_blocks(
                job_name=job_name,
                project_name=project_name,
                execution_id=execution_id,
                started_at=started_at,
                summary=summary,
                status=status,
                base_url=base_url,
                pdf_path=pdf_path,
                is_failure=is_failure,
            )

            # Monta payload
            payload: dict = {
                'username': self._username,
                'icon_emoji': self._icon_emoji,
                'blocks': blocks,
            }

            if self._channel:
                payload['channel'] = self._channel

            # Texto fallback para notificacoes
            fallback_text = f'AgentVision - {job_name}: {status}'
            if is_failure and self._mention_on_failure:
                fallback_text = f'<!here> {fallback_text}'
            payload['text'] = fallback_text

            # Envia para o webhook
            response = requests.post(
                self._webhook_url,
                json=payload,
                timeout=_SLACK_TIMEOUT,
                headers={'Content-Type': 'application/json'},
            )

            if response.status_code == 200 and response.text == 'ok':
                logger.info(
                    'Mensagem Slack enviada com sucesso para job %s',
                    job_name,
                )
                return DeliveryResult(success=True)

            error_msg = (
                f'Slack webhook retornou status {response.status_code}: '
                f'{response.text[:200]}'
            )
            logger.error(error_msg)
            return DeliveryResult(success=False, error_message=error_msg)

        except requests.exceptions.Timeout:
            error_msg = 'Timeout ao enviar mensagem para o Slack'
            logger.error(error_msg)
            return DeliveryResult(success=False, error_message=error_msg)

        except requests.exceptions.ConnectionError as e:
            error_msg = f'Erro de conexao com Slack: {str(e)[:200]}'
            logger.error(error_msg)
            return DeliveryResult(success=False, error_message=error_msg)

        except Exception as e:
            error_msg = f'Erro inesperado ao enviar para Slack: {str(e)[:200]}'
            logger.error(error_msg)
            return DeliveryResult(success=False, error_message=error_msg)

    def _build_blocks(
        self,
        job_name: str,
        project_name: str,
        execution_id: str,
        started_at: str,
        summary: str,
        status: str,
        base_url: str,
        pdf_path: str | None,
        is_failure: bool,
    ) -> list[dict]:
        """Constroi blocos Slack Block Kit para a mensagem."""
        # Emoji e cor por status
        status_emoji = ':white_check_mark:' if not is_failure else ':x:'
        status_label = 'Concluido' if not is_failure else 'Falhou'

        blocks: list[dict] = []

        # Header
        blocks.append({
            'type': 'header',
            'text': {
                'type': 'plain_text',
                'text': f'{status_emoji} AgentVision - Relatorio de Execucao',
                'emoji': True,
            },
        })

        # Mention @here em caso de falha
        if is_failure and self._mention_on_failure:
            blocks.append({
                'type': 'section',
                'text': {
                    'type': 'mrkdwn',
                    'text': '<!here> *Atencao: execucao falhou!*',
                },
            })

        # Detalhes do job
        blocks.append({
            'type': 'section',
            'fields': [
                {
                    'type': 'mrkdwn',
                    'text': f'*Projeto:*\n{project_name}',
                },
                {
                    'type': 'mrkdwn',
                    'text': f'*Job:*\n{job_name}',
                },
                {
                    'type': 'mrkdwn',
                    'text': f'*Status:*\n{status_emoji} {status_label}',
                },
                {
                    'type': 'mrkdwn',
                    'text': f'*Data:*\n{started_at}',
                },
            ],
        })

        # Divider
        blocks.append({'type': 'divider'})

        # Sumario executivo (truncado a 500 caracteres para o Slack)
        if summary:
            truncated = summary[:500]
            if len(summary) > 500:
                truncated += '...'
            blocks.append({
                'type': 'section',
                'text': {
                    'type': 'mrkdwn',
                    'text': f'*Resumo Executivo:*\n{truncated}',
                },
            })
            blocks.append({'type': 'divider'})

        # Link para PDF (se disponivel)
        if pdf_path:
            blocks.append({
                'type': 'section',
                'text': {
                    'type': 'mrkdwn',
                    'text': f':page_facing_up: *PDF disponivel no storage:* `{pdf_path}`',
                },
            })

        # URL monitorada
        if base_url:
            blocks.append({
                'type': 'section',
                'text': {
                    'type': 'mrkdwn',
                    'text': f':globe_with_meridians: *URL monitorada:* {base_url}',
                },
            })

        # Context (footer)
        blocks.append({
            'type': 'context',
            'elements': [
                {
                    'type': 'mrkdwn',
                    'text': (
                        f'Execution ID: `{execution_id}` | '
                        f'Gerado automaticamente pelo AgentVision'
                    ),
                },
            ],
        })

        return blocks
