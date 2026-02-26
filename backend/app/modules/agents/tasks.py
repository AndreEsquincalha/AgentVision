"""
Tasks Celery do modulo agents.

Contem:
- check_llm_providers_health: health check periodico dos providers LLM (13.1.4)
"""

import logging

from app.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name='app.modules.agents.tasks.check_llm_providers_health',
    ignore_result=True,
)
def check_llm_providers_health() -> dict:
    """
    Task periodica que verifica a saude dos providers LLM configurados.

    Busca todos os providers com API key configurada nas Settings,
    testa cada um com um prompt minimo, e salva o resultado no Redis.

    Roda a cada 10 minutos via Celery Beat.

    Returns:
        Dict com resultado do health check de cada provider testado.
    """
    from app.database import SessionLocal
    from app.modules.agents.llm_resilience import (
        check_provider_health,
        save_health_status,
    )
    from app.modules.settings.repository import SettingRepository
    from app.shared.utils import decrypt_value

    logger.info('Iniciando health check dos providers LLM')

    results = {}
    db = SessionLocal()

    try:
        setting_repo = SettingRepository(db)

        # Busca providers configurados nas Settings
        # As API keys sao armazenadas como settings com chaves como
        # 'llm.anthropic.api_key', 'llm.openai.api_key', etc.
        # Tambem busca configuracoes de projetos ativos

        from app.modules.projects.models import Project

        projects = (
            db.query(Project)
            .filter(
                Project.is_active.is_(True),
                Project.deleted_at.is_(None),
            )
            .all()
        )

        # Coleta providers unicos com suas configuracoes
        providers_to_check: dict[str, dict] = {}

        for project in projects:
            provider = project.llm_provider
            if provider in providers_to_check:
                continue

            # Descriptografa API key do projeto
            api_key = ''
            if project.encrypted_llm_api_key:
                try:
                    api_key = decrypt_value(project.encrypted_llm_api_key)
                except Exception:
                    logger.debug(
                        'Nao foi possivel descriptografar API key do '
                        'projeto %s para provider %s',
                        project.name, provider,
                    )
                    continue

            # Ollama nao precisa de API key
            if provider == 'ollama' or api_key:
                providers_to_check[provider] = {
                    'api_key': api_key,
                    'model': project.llm_model,
                }

        if not providers_to_check:
            logger.info('Nenhum provider LLM configurado para health check')
            return {'message': 'Nenhum provider configurado'}

        # Testa cada provider
        for provider_name, config in providers_to_check.items():
            logger.info('Testando provider LLM: %s', provider_name)

            status = check_provider_health(
                provider_name=provider_name,
                api_key=config['api_key'],
                model=config['model'],
            )

            save_health_status(status)

            results[provider_name] = {
                'status': status.status,
                'latency_ms': status.latency_ms,
                'error': status.error,
            }

            logger.info(
                'Health check %s: status=%s, latencia=%.0fms%s',
                provider_name,
                status.status,
                status.latency_ms,
                f', erro={status.error}' if status.error else '',
            )

    except Exception as e:
        logger.error('Erro no health check dos providers LLM: %s', str(e))
        results['error'] = str(e)

    finally:
        db.close()

    logger.info('Health check concluido: %s', results)
    return results
