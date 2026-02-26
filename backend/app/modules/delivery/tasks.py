"""
Tasks Celery para o modulo de delivery.

Contem tasks assincronas para retry automatico de entregas falhadas.
"""

import logging

from celery import shared_task

from app.database import SessionLocal
from app.modules.delivery.repository import DeliveryRepository
from app.modules.delivery.service import DeliveryService

logger = logging.getLogger(__name__)


@shared_task(
    name='app.modules.delivery.tasks.retry_failed_delivery',
    bind=True,
    max_retries=0,
    acks_late=True,
)
def retry_failed_delivery(
    self,
    delivery_log_id: str,
    pdf_path: str | None = None,
    execution_data: dict | None = None,
) -> dict:
    """
    Retenta uma entrega que falhou, com backoff exponencial.

    Esta task e agendada automaticamente pelo DeliveryService quando
    uma entrega falha e ainda ha retries disponiveis.

    Args:
        delivery_log_id: ID do log de entrega a ser retentado.
        pdf_path: Caminho do PDF no storage.
        execution_data: Dados da execucao original.

    Returns:
        Dicionario com resultado do retry.
    """
    import uuid

    log_uuid = uuid.UUID(delivery_log_id)

    db = SessionLocal()
    try:
        repository = DeliveryRepository(db)
        service = DeliveryService(repository)

        # Busca o log
        log = repository.get_log_by_id(log_uuid)
        if not log:
            logger.warning(
                'Retry: log de entrega %s nao encontrado',
                delivery_log_id,
            )
            return {'success': False, 'error': 'Log nao encontrado'}

        # Verifica se ainda esta em status retrying
        if log.status != 'retrying':
            logger.info(
                'Retry: log %s nao esta em status retrying (status=%s)',
                delivery_log_id, log.status,
            )
            return {'success': False, 'error': f'Status inesperado: {log.status}'}

        # Busca a configuracao de entrega
        config = repository.get_config_by_id(log.delivery_config_id)
        if not config:
            logger.warning(
                'Retry: config %s nao encontrada para log %s',
                log.delivery_config_id, delivery_log_id,
            )
            repository.update_log(log.id, {
                'status': 'failed',
                'error_message': 'Configuracao de entrega nao encontrada',
                'next_retry_at': None,
            })
            return {'success': False, 'error': 'Config nao encontrada'}

        # Tenta enviar novamente
        decrypted_config = service._decrypt_channel_config(config.channel_config)
        channel = service._create_channel(config.channel_type, decrypted_config)

        from app.modules.delivery.base_channel import DeliveryResult
        from app.shared.utils import utc_now

        result: DeliveryResult = channel.send(
            recipients=config.recipients or [],
            pdf_path=pdf_path,
            config=decrypted_config,
            execution_data=execution_data,
        )

        if result.success:
            repository.update_log(log.id, {
                'status': 'sent',
                'sent_at': utc_now(),
                'error_message': None,
                'next_retry_at': None,
            })
            logger.info(
                'Retry bem-sucedido para log %s (tentativa %d)',
                delivery_log_id, log.retry_count,
            )
            return {'success': True, 'log_id': delivery_log_id}
        else:
            # Agenda proximo retry ou marca como falha definitiva
            service._schedule_retry_or_fail(
                log, config, result.error_message, pdf_path, execution_data,
            )
            logger.warning(
                'Retry falhou para log %s (tentativa %d): %s',
                delivery_log_id, log.retry_count, result.error_message,
            )
            return {
                'success': False,
                'log_id': delivery_log_id,
                'error': result.error_message,
            }

    except Exception as e:
        logger.error(
            'Erro inesperado no retry de delivery %s: %s',
            delivery_log_id, str(e),
        )
        return {'success': False, 'error': str(e)}
    finally:
        db.close()
