from redis import Redis

from app.config import settings


def get_redis_client() -> Redis:
    """Retorna uma instancia do cliente Redis usando a URL das configuracoes."""
    return Redis.from_url(settings.redis_url, decode_responses=True)
