"""
Tasks Celery para avaliacao periodica de alertas.
"""

import logging

from app.celery_app import celery_app
from app.database import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(name='app.modules.alerts.tasks.evaluate_alert_rules')
def evaluate_alert_rules() -> dict:
    """
    Task periodica que avalia todas as regras de alerta ativas.

    Roda a cada 2 minutos via Celery Beat.
    Verifica condicoes, respeita cooldown e dispara notificacoes.
    """
    from app.modules.alerts.service import AlertService

    db = SessionLocal()
    try:
        service = AlertService(db)
        fired = service.evaluate_all_rules()

        if fired:
            logger.info(
                'Avaliacao de alertas concluida: %d alerta(s) disparado(s)',
                len(fired),
            )
        else:
            logger.debug('Avaliacao de alertas concluida: nenhum alerta disparado')

        return {
            'status': 'ok',
            'alerts_fired': len(fired),
            'details': fired,
        }
    except Exception as e:
        logger.error('Erro na avaliacao de alertas: %s', str(e))
        return {'status': 'error', 'error': str(e)[:500]}
    finally:
        db.close()
