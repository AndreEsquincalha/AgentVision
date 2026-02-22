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
)

# Autodiscover de tasks em todos os modulos
celery_app.autodiscover_tasks([
    'app.modules.jobs',
])
