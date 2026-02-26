from celery import Celery

from app.config import settings

# Instancia do Celery configurada com Redis como broker e backend
celery_app = Celery(
    'agentvision',
    broker=settings.redis_url,
    backend=settings.redis_url,
)

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
    },
)

# Autodiscover de tasks em todos os modulos
celery_app.autodiscover_tasks([
    'app.modules.jobs',
    'app.modules.auth',
])
