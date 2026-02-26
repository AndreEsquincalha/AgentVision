from celery import Celery, signals

from app.config import settings
from app.shared.logging import (
    correlation_id_var,
    generate_id,
    get_logger,
    request_id_var,
    setup_logging,
)

# Inicializa logging estruturado para workers Celery
setup_logging(
    log_level=settings.log_level,
    log_format=settings.log_format,
    log_levels=settings.log_levels,
)

logger = get_logger(__name__)

# Instancia do Celery configurada com Redis como broker e backend
celery_app = Celery(
    'agentvision',
    broker=settings.redis_url,
    backend=settings.redis_url,
)


# ---------------------------------------------------------------------------
# Propagacao de request_id/correlation_id via headers Celery
# ---------------------------------------------------------------------------

@signals.before_task_publish.connect
def propagate_context_to_task(headers: dict, **kwargs) -> None:
    """Propaga request_id e correlation_id para tasks Celery via headers."""
    req_id = request_id_var.get()
    corr_id = correlation_id_var.get()
    if req_id:
        headers['x_request_id'] = req_id
    if corr_id:
        headers['x_correlation_id'] = corr_id


@signals.task_prerun.connect
def restore_context_in_task(task_id: str, task: object, **kwargs) -> None:
    """Restaura request_id e correlation_id do header da task Celery."""
    request = getattr(task, 'request', None)
    if not request:
        return

    # Ler headers propagados ou gerar novos
    req_id = getattr(request, 'x_request_id', None) or generate_id()
    corr_id = getattr(request, 'x_correlation_id', None) or generate_id()

    request_id_var.set(req_id)
    correlation_id_var.set(corr_id)

    logger.info(
        'task_started',
        task_name=getattr(request, 'task', 'unknown'),
        celery_task_id=task_id,
    )


@signals.task_postrun.connect
def clear_context_after_task(task_id: str, **kwargs) -> None:
    """Limpa context vars apos execucao da task."""
    request_id_var.set(None)
    correlation_id_var.set(None)

# Configuracoes do Celery
celery_app.conf.update(
    # Serializacao
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',

    # Timezone
    timezone='UTC',
    enable_utc=True,

    # Configuracoes de retry e execucao
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,

    # Resultados expiram em 24 horas
    result_expires=86400,

    # Autodiscover de tasks nos modulos
    task_routes={
        'app.modules.jobs.tasks.*': {'queue': 'default'},
    },

    # Celery Beat: agendamento periodico
    # A task check_and_dispatch_jobs roda a cada minuto e verifica
    # quais jobs ativos devem ser disparados com base em seus crons.
    # Isso permite agendamento dinamico sem necessidade de RedBeat
    # ou DatabaseScheduler — basta ativar/desativar jobs no banco.
    #
    # A task cleanup_stale_executions roda a cada 5 minutos e recupera
    # execucoes orfas (running ha mais de 30 min sem heartbeat),
    # marcando-as como failed e liberando locks Redis.
    beat_schedule={
        'check-and-dispatch-jobs-every-minute': {
            'task': 'app.modules.jobs.tasks.check_and_dispatch_jobs',
            'schedule': 60.0,  # a cada 60 segundos
        },
        'cleanup-stale-executions-every-5-minutes': {
            'task': 'app.modules.jobs.tasks.cleanup_stale_executions',
            'schedule': 300.0,  # a cada 5 minutos (300 segundos)
        },
        'cleanup-token-blacklist-every-hour': {
            'task': 'app.modules.auth.tasks.cleanup_token_blacklist',
            'schedule': 3600.0,
        },
        'check-llm-providers-health-every-10-minutes': {
            'task': 'app.modules.agents.tasks.check_llm_providers_health',
            'schedule': 600.0,  # a cada 10 minutos
        },
        'evaluate-alert-rules-every-2-minutes': {
            'task': 'app.modules.alerts.tasks.evaluate_alert_rules',
            'schedule': 120.0,  # a cada 2 minutos
        },
    },
)

# Autodiscover de tasks em todos os modulos
celery_app.autodiscover_tasks([
    'app.modules.jobs',
    'app.modules.auth',
    'app.modules.agents',
    'app.modules.alerts',
])
