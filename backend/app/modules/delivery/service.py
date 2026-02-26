import logging
import uuid

from app.config import settings
from app.modules.delivery.base_channel import DeliveryChannel, DeliveryResult
from app.modules.delivery.email_channel import EmailChannel
from app.modules.delivery.models import DeliveryConfig
from app.modules.delivery.slack_channel import SlackChannel
from app.modules.delivery.storage_channel import StorageChannel
from app.modules.delivery.webhook_channel import WebhookChannel
from app.modules.delivery.repository import DeliveryRepository
from app.modules.delivery.schemas import (
    DeliveryConfigCreate,
    DeliveryConfigResponse,
    DeliveryConfigUpdate,
    DeliveryLogResponse,
)
from app.shared.exceptions import BadRequestException, NotFoundException
from app.shared.security import mask_sensitive_dict
from app.shared.utils import decrypt_dict, encrypt_dict, utc_now

logger = logging.getLogger(__name__)


class DeliveryService:
    """
    Servico de entrega.

    Contem a logica de negocio para gerenciamento de configuracoes de entrega
    e execucao de entregas atraves dos canais configurados (Strategy Pattern).
    """

    def __init__(self, repository: DeliveryRepository) -> None:
        """Inicializa o servico com o repositorio de entregas."""
        self._repository = repository

    # -------------------------------------------------------------------------
    # Gerenciamento de configuracoes de entrega
    # -------------------------------------------------------------------------

    def get_configs_by_job(self, job_id: uuid.UUID) -> list[DeliveryConfigResponse]:
        """
        Lista configuracoes de entrega de um job.

        Args:
            job_id: ID do job.

        Returns:
            Lista de configuracoes de entrega.
        """
        configs = self._repository.get_configs_by_job(job_id)
        return [self._to_response(config) for config in configs]

    def get_config(self, config_id: uuid.UUID) -> DeliveryConfigResponse:
        """
        Busca uma configuracao de entrega pelo ID.

        Args:
            config_id: ID da configuracao.

        Returns:
            Dados da configuracao de entrega.

        Raises:
            NotFoundException: Se a configuracao nao for encontrada.
        """
        config = self._repository.get_config_by_id(config_id)
        if not config:
            raise NotFoundException('Configuracao de entrega nao encontrada')
        return self._to_response(config)

    def create_config(self, data: DeliveryConfigCreate) -> DeliveryConfigResponse:
        """
        Cria uma nova configuracao de entrega.

        Args:
            data: Dados da configuracao a ser criada.

        Returns:
            Dados da configuracao criada.
        """
        encrypted_config = (
            encrypt_dict(data.channel_config) if data.channel_config else None
        )
        config_data: dict = {
            'job_id': data.job_id,
            'channel_type': data.channel_type,
            'recipients': data.recipients,
            'channel_config': encrypted_config,
            'is_active': data.is_active,
            'max_retries': data.max_retries,
            'retry_delay_seconds': data.retry_delay_seconds,
            'delivery_condition': data.delivery_condition,
            'email_template_id': data.email_template_id,
        }
        config = self._repository.create_config(config_data)
        return self._to_response(config)

    def update_config(
        self,
        config_id: uuid.UUID,
        data: DeliveryConfigUpdate,
    ) -> DeliveryConfigResponse:
        """
        Atualiza uma configuracao de entrega existente.

        Args:
            config_id: ID da configuracao a ser atualizada.
            data: Dados a serem atualizados.

        Returns:
            Dados da configuracao atualizada.

        Raises:
            NotFoundException: Se a configuracao nao for encontrada.
        """
        existing = self._repository.get_config_by_id(config_id)
        if not existing:
            raise NotFoundException('Configuracao de entrega nao encontrada')

        update_data = self._prepare_config_update_data(data)

        if not update_data:
            return self._to_response(existing)

        config = self._repository.update_config(config_id, update_data)
        if not config:
            raise NotFoundException('Configuracao de entrega nao encontrada')

        return self._to_response(config)

    def delete_config(self, config_id: uuid.UUID) -> None:
        """
        Realiza soft delete de uma configuracao de entrega.

        Args:
            config_id: ID da configuracao a ser excluida.

        Raises:
            NotFoundException: Se a configuracao nao for encontrada.
        """
        success = self._repository.delete_config(config_id)
        if not success:
            raise NotFoundException('Configuracao de entrega nao encontrada')

    # -------------------------------------------------------------------------
    # Execucao de entregas
    # -------------------------------------------------------------------------

    def deliver(
        self,
        execution_id: uuid.UUID,
        delivery_configs: list[DeliveryConfig],
        pdf_path: str | None = None,
        execution_data: dict | None = None,
        execution_status: str = 'success',
        extracted_data: dict | None = None,
        previous_extracted_data: dict | None = None,
    ) -> list[DeliveryLogResponse]:
        """
        Executa entregas para todos os canais configurados.

        Para cada configuracao de entrega ativa, instancia o canal
        apropriado (Strategy Pattern), avalia a condicao de entrega,
        tenta enviar e registra o resultado.

        Args:
            execution_id: ID da execucao.
            delivery_configs: Lista de configuracoes de entrega.
            pdf_path: Caminho do PDF no storage.
            execution_data: Dados da execucao para incluir na entrega.
            execution_status: Status da execucao (success, failed).
            extracted_data: Dados extraidos da execucao atual.
            previous_extracted_data: Dados extraidos da execucao anterior (para on_change).

        Returns:
            Lista de logs de entrega com resultados.
        """
        log_responses: list[DeliveryLogResponse] = []

        for config in delivery_configs:
            # Ignora configuracoes inativas
            if not config.is_active:
                continue

            # Avalia condicao de entrega
            if not self._evaluate_delivery_condition(
                config, execution_status, extracted_data, previous_extracted_data,
            ):
                logger.info(
                    'Entrega ignorada para config %s: condicao "%s" nao atendida (status=%s)',
                    config.id, config.delivery_condition, execution_status,
                )
                continue

            # Cria log com status pendente
            log = self._repository.create_log({
                'execution_id': execution_id,
                'delivery_config_id': config.id,
                'channel_type': config.channel_type,
                'status': 'pending',
            })

            try:
                # Instancia o canal correto via Factory
                decrypted_config = self._decrypt_channel_config(config.channel_config)

                # Injeta template de email customizado, se configurado
                if (
                    config.channel_type == 'email'
                    and config.email_template_id
                ):
                    template_content = self._load_email_template(config.email_template_id)
                    if template_content:
                        decrypted_config = decrypted_config or {}
                        decrypted_config['_email_template_content'] = template_content

                channel = self._create_channel(config.channel_type, decrypted_config)

                # Executa a entrega
                result: DeliveryResult = channel.send(
                    recipients=config.recipients or [],
                    pdf_path=pdf_path,
                    config=decrypted_config,
                    execution_data=execution_data,
                )

                # Atualiza o log com o resultado
                if result.success:
                    self._repository.update_log(log.id, {
                        'status': 'sent',
                        'sent_at': utc_now(),
                    })
                else:
                    self._schedule_retry_or_fail(
                        log, config, result.error_message, pdf_path, execution_data,
                    )

            except Exception as e:
                logger.error(
                    'Erro ao executar entrega para config %s: %s',
                    config.id,
                    str(e),
                )
                self._schedule_retry_or_fail(
                    log, config, f'Erro inesperado: {str(e)}', pdf_path, execution_data,
                )

            # Recarrega o log atualizado
            updated_log = self._repository.get_log_by_id(log.id)
            if updated_log:
                log_responses.append(
                    DeliveryLogResponse.model_validate(updated_log)
                )

        return log_responses

    def retry_delivery(self, delivery_log_id: uuid.UUID) -> DeliveryLogResponse:
        """
        Retenta uma entrega que falhou.

        Busca o log original, verifica que falhou, e tenta novamente
        com as mesmas configuracoes.

        Args:
            delivery_log_id: ID do log de entrega a ser retentado.

        Returns:
            Log de entrega atualizado.

        Raises:
            NotFoundException: Se o log nao for encontrado.
            BadRequestException: Se o log nao estiver em status 'failed'.
        """
        log = self._repository.get_log_by_id(delivery_log_id)
        if not log:
            raise NotFoundException('Log de entrega nao encontrado')

        if log.status != 'failed':
            raise BadRequestException(
                'Somente entregas com status "failed" podem ser retentadas'
            )

        # Busca a configuracao de entrega original
        config = self._repository.get_config_by_id(log.delivery_config_id)
        if not config:
            raise NotFoundException('Configuracao de entrega nao encontrada')

        try:
            # Instancia o canal e tenta novamente
            decrypted_config = self._decrypt_channel_config(config.channel_config)
            channel = self._create_channel(config.channel_type, decrypted_config)
            result: DeliveryResult = channel.send(
                recipients=config.recipients or [],
                pdf_path=None,  # PDF pode nao estar mais disponivel localmente
                config=decrypted_config,
            )

            if result.success:
                self._repository.update_log(log.id, {
                    'status': 'sent',
                    'sent_at': utc_now(),
                    'error_message': None,
                })
            else:
                self._repository.update_log(log.id, {
                    'status': 'failed',
                    'error_message': result.error_message,
                })

        except Exception as e:
            logger.error(
                'Erro ao retentar entrega %s: %s',
                delivery_log_id,
                str(e),
            )
            self._repository.update_log(log.id, {
                'status': 'failed',
                'error_message': f'Erro ao retentar: {str(e)}',
            })

        # Recarrega o log atualizado
        updated_log = self._repository.get_log_by_id(log.id)
        if not updated_log:
            raise NotFoundException('Log de entrega nao encontrado apos atualizacao')

        return DeliveryLogResponse.model_validate(updated_log)

    def get_logs_by_execution(
        self,
        execution_id: uuid.UUID,
    ) -> list[DeliveryLogResponse]:
        """
        Busca logs de entrega de uma execucao.

        Args:
            execution_id: ID da execucao.

        Returns:
            Lista de logs de entrega.
        """
        logs = self._repository.get_logs_by_execution(execution_id)
        return [
            DeliveryLogResponse.model_validate(log)
            for log in logs
        ]

    # -------------------------------------------------------------------------
    # Factory: instancia o canal correto (Strategy Pattern)
    # -------------------------------------------------------------------------

    def _create_channel(
        self,
        channel_type: str,
        channel_config: dict | None = None,
    ) -> DeliveryChannel:
        """
        Factory method que instancia o canal de entrega correto.

        Args:
            channel_type: Tipo do canal (email, webhook).
            channel_config: Configuracoes especificas do canal.

        Returns:
            Instancia do canal de entrega.

        Raises:
            BadRequestException: Se o tipo de canal nao for suportado.
        """
        if channel_type == 'email':
            return self._create_email_channel(channel_config)
        elif channel_type == 'webhook':
            return self._create_webhook_channel(channel_config)
        elif channel_type == 'slack':
            return self._create_slack_channel(channel_config)
        elif channel_type == 'storage':
            return self._create_storage_channel(channel_config)
        else:
            raise BadRequestException(
                f'Tipo de canal nao suportado: {channel_type}'
            )

    def _create_email_channel(
        self,
        channel_config: dict | None = None,
    ) -> EmailChannel:
        """
        Cria uma instancia do canal de email com configuracoes SMTP.

        Tenta carregar configuracoes do channel_config fornecido,
        ou utiliza variaveis de ambiente como fallback.

        Args:
            channel_config: Configuracoes SMTP especificas (opcional).

        Returns:
            Instancia de EmailChannel configurada.

        Raises:
            BadRequestException: Se as configuracoes SMTP nao estiverem disponiveis.
        """
        # Tenta usar configuracoes do channel_config, se disponivel
        smtp_host = (channel_config or {}).get(
            'smtp_host',
            getattr(settings, 'smtp_host', ''),
        )
        smtp_port = (channel_config or {}).get(
            'smtp_port',
            getattr(settings, 'smtp_port', 587),
        )
        smtp_user = (channel_config or {}).get(
            'smtp_user',
            getattr(settings, 'smtp_user', ''),
        )
        smtp_password = (channel_config or {}).get(
            'smtp_password',
            getattr(settings, 'smtp_password', ''),
        )
        smtp_from = (channel_config or {}).get(
            'smtp_from',
            getattr(settings, 'smtp_from', ''),
        )
        smtp_use_tls = (channel_config or {}).get(
            'smtp_use_tls',
            getattr(settings, 'smtp_use_tls', True),
        )

        if not smtp_host:
            raise BadRequestException(
                'Configuracoes SMTP nao encontradas. '
                'Configure o SMTP nas configuracoes do sistema ou no canal de entrega.'
            )

        return EmailChannel(
            smtp_host=smtp_host,
            smtp_port=int(smtp_port),
            smtp_user=smtp_user,
            smtp_password=smtp_password,
            smtp_from=smtp_from,
            smtp_use_tls=bool(smtp_use_tls),
        )

    @staticmethod
    def _evaluate_delivery_condition(
        config: DeliveryConfig,
        execution_status: str,
        extracted_data: dict | None,
        previous_extracted_data: dict | None,
    ) -> bool:
        """
        Avalia se a condicao de entrega e atendida.

        Args:
            config: Configuracao de entrega com delivery_condition.
            execution_status: Status da execucao (success, failed).
            extracted_data: Dados extraidos da execucao atual.
            previous_extracted_data: Dados extraidos da execucao anterior.

        Returns:
            True se a entrega deve ser realizada.
        """
        condition = config.delivery_condition

        if condition == 'always':
            return True
        elif condition == 'on_success':
            return execution_status == 'success'
        elif condition == 'on_failure':
            return execution_status in ('failed', 'error')
        elif condition == 'on_change':
            # Compara dados extraidos com a execucao anterior
            if previous_extracted_data is None:
                # Primeira execucao — sempre entrega
                return True
            # Compara JSON stringificado (ordenado) para detectar mudancas
            import json
            current = json.dumps(extracted_data or {}, sort_keys=True, default=str)
            previous = json.dumps(previous_extracted_data, sort_keys=True, default=str)
            return current != previous
        else:
            # Condicao desconhecida — entrega por seguranca
            return True

    def _schedule_retry_or_fail(
        self,
        log: object,
        config: DeliveryConfig,
        error_message: str | None,
        pdf_path: str | None,
        execution_data: dict | None,
    ) -> None:
        """
        Agenda retry automatico ou marca como falha definitiva.

        Calcula o proximo retry com backoff exponencial (multiplicador 2.0)
        e agenda a task Celery retry_failed_delivery.
        """
        from datetime import timedelta

        current_retry = getattr(log, 'retry_count', 0)
        max_retries = config.max_retries

        if current_retry < max_retries:
            # Calcula delay com backoff exponencial
            base_delay = config.retry_delay_seconds
            delay = base_delay * (2 ** current_retry)  # 60s, 120s, 240s...
            delay = min(delay, 3600)  # Cap em 1 hora

            next_retry = utc_now() + timedelta(seconds=delay)

            self._repository.update_log(log.id, {
                'status': 'retrying',
                'error_message': error_message,
                'retry_count': current_retry + 1,
                'next_retry_at': next_retry,
            })

            # Agenda task Celery para retry
            try:
                from app.modules.delivery.tasks import retry_failed_delivery
                retry_failed_delivery.apply_async(
                    args=[str(log.id), pdf_path, execution_data],
                    countdown=delay,
                    queue='default',
                )
                logger.info(
                    'Retry %d/%d agendado para log %s em %ds',
                    current_retry + 1, max_retries, log.id, delay,
                )
            except Exception as e:
                logger.warning(
                    'Falha ao agendar retry para log %s: %s',
                    log.id, str(e),
                )
                # Se nao conseguiu agendar, marca como failed
                self._repository.update_log(log.id, {
                    'status': 'failed',
                    'error_message': error_message,
                    'next_retry_at': None,
                })
        else:
            # Sem mais retries — marca como falha definitiva
            self._repository.update_log(log.id, {
                'status': 'failed',
                'error_message': error_message,
                'next_retry_at': None,
            })

    def _create_webhook_channel(
        self,
        channel_config: dict | None = None,
    ) -> WebhookChannel:
        """
        Cria uma instancia do canal webhook.

        Args:
            channel_config: Configuracoes do webhook (url, method, headers, auth).

        Returns:
            Instancia de WebhookChannel configurada.
        """
        config = channel_config or {}
        url = config.get('url', '')
        if not url:
            raise BadRequestException(
                'URL do webhook nao configurada. '
                'Configure o campo "url" nas configuracoes do canal.'
            )

        return WebhookChannel(
            url=url,
            method=config.get('method', 'POST'),
            headers=config.get('headers'),
            auth_type=config.get('auth_type'),
            auth_token=config.get('auth_token'),
            auth_user=config.get('auth_user'),
            auth_password=config.get('auth_password'),
            verify_ssl=config.get('verify_ssl', True),
        )

    def _create_slack_channel(
        self,
        channel_config: dict | None = None,
    ) -> SlackChannel:
        """
        Cria uma instancia do canal Slack.

        Args:
            channel_config: Configuracoes do Slack (webhook_url, channel, etc.).

        Returns:
            Instancia de SlackChannel configurada.
        """
        config = channel_config or {}
        webhook_url = config.get('webhook_url', '')
        if not webhook_url:
            raise BadRequestException(
                'URL do webhook Slack nao configurada. '
                'Configure o campo "webhook_url" nas configuracoes do canal.'
            )

        return SlackChannel(
            webhook_url=webhook_url,
            channel=config.get('channel'),
            mention_on_failure=config.get('mention_on_failure', True),
            username=config.get('username', 'AgentVision'),
            icon_emoji=config.get('icon_emoji', ':robot_face:'),
        )

    def _create_storage_channel(
        self,
        channel_config: dict | None = None,
    ) -> StorageChannel:
        """
        Cria uma instancia do canal de armazenamento.

        Args:
            channel_config: Configuracoes do storage (storage_type, path_template, etc.).

        Returns:
            Instancia de StorageChannel configurada.
        """
        config = channel_config or {}

        return StorageChannel(
            storage_type=config.get('storage_type', 'local'),
            path_template=config.get(
                'path_template',
                '{project}/{job}/{date}/report.pdf',
            ),
            base_path=config.get('base_path', '/data/reports'),
            s3_bucket=config.get('s3_bucket'),
            s3_endpoint=config.get('s3_endpoint'),
            s3_access_key=config.get('s3_access_key'),
            s3_secret_key=config.get('s3_secret_key'),
        )

    # -------------------------------------------------------------------------
    # Metodos auxiliares privados
    # -------------------------------------------------------------------------

    def _prepare_config_update_data(self, data: DeliveryConfigUpdate) -> dict:
        """
        Prepara os dados para atualizacao de configuracao de entrega.

        Apenas campos com valores nao-None sao incluidos no dicionario.

        Args:
            data: Dados do schema de atualizacao.

        Returns:
            Dicionario com campos a atualizar.
        """
        update_data: dict = {}

        fields = [
            'channel_type', 'recipients', 'channel_config', 'is_active',
            'max_retries', 'retry_delay_seconds', 'delivery_condition',
            'email_template_id',
        ]

        for field in fields:
            value = getattr(data, field)
            if value is not None:
                if field == 'channel_config':
                    update_data[field] = encrypt_dict(value)
                else:
                    update_data[field] = value

        return update_data

    def _load_email_template(self, template_id: uuid.UUID) -> str | None:
        """
        Carrega o conteudo de um template de email customizado.

        Args:
            template_id: ID do PromptTemplate.

        Returns:
            Conteudo HTML do template ou None se nao encontrado.
        """
        try:
            from app.modules.prompts.models import PromptTemplate
            from sqlalchemy import select

            stmt = select(PromptTemplate).where(
                PromptTemplate.id == template_id,
                PromptTemplate.deleted_at.is_(None),
            )
            template = self._repository._db.execute(stmt).scalar_one_or_none()
            if template:
                return template.content
            logger.warning(
                'Template de email %s nao encontrado, usando template padrao',
                template_id,
            )
        except Exception as e:
            logger.warning(
                'Erro ao carregar template de email %s: %s',
                template_id, str(e),
            )
        return None

    def _decrypt_channel_config(self, encrypted_value: str | None) -> dict | None:
        """
        Descriptografa channel_config (se houver).
        """
        if not encrypted_value:
            return None
        try:
            return decrypt_dict(encrypted_value)
        except Exception:
            logger.warning('Nao foi possivel descriptografar channel_config')
            return None

    def _to_response(self, config: DeliveryConfig) -> DeliveryConfigResponse:
        """
        Converte modelo para resposta mascarando dados sensiveis.
        """
        decrypted = self._decrypt_channel_config(config.channel_config)
        masked = mask_sensitive_dict(decrypted) if decrypted else None
        return DeliveryConfigResponse(
            id=config.id,
            job_id=config.job_id,
            channel_type=config.channel_type,
            recipients=config.recipients,
            channel_config=masked,
            is_active=config.is_active,
            max_retries=config.max_retries,
            retry_delay_seconds=config.retry_delay_seconds,
            delivery_condition=config.delivery_condition,
            email_template_id=config.email_template_id,
            created_at=config.created_at,
            updated_at=config.updated_at,
        )
