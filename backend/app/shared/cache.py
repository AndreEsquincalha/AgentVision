"""
Modulo de cache Redis para queries frequentes.

Fornece o decorator @cached(ttl=N) para cachear resultados de funcoes,
e funcoes auxiliares para invalidacao de cache por prefixo.
"""

import functools
import hashlib
import json
import logging
from typing import Any

from app.shared.redis_client import get_redis_client

logger = logging.getLogger(__name__)

# Prefixo global para todas as chaves de cache
_CACHE_PREFIX = 'cache:'


def _make_cache_key(prefix: str, args: tuple, kwargs: dict) -> str:
    """Gera chave de cache deterministica a partir de prefix + argumentos."""
    # Serializa argumentos de forma deterministica
    key_data = json.dumps({'a': [str(a) for a in args], 'k': {str(k): str(v) for k, v in sorted(kwargs.items())}}, sort_keys=True)
    key_hash = hashlib.md5(key_data.encode()).hexdigest()[:16]
    return f'{_CACHE_PREFIX}{prefix}:{key_hash}'


def cached(ttl: int = 60, prefix: str | None = None):
    """
    Decorator que cacheia o resultado de uma funcao no Redis.

    Args:
        ttl: Tempo de vida do cache em segundos (default: 60).
        prefix: Prefixo customizado para a chave. Se None, usa nome da funcao.

    Uso:
        @cached(ttl=300, prefix='dashboard:summary')
        def get_summary(self):
            ...

    O cache e invalidado automaticamente apos o TTL.
    Para invalidacao manual, use invalidate_cache(prefix).
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            cache_prefix = prefix or f'{func.__module__}.{func.__qualname__}'
            # Ignora 'self' nos argumentos para metodos de instancia
            cache_args = args[1:] if args and hasattr(args[0], '__class__') else args
            cache_key = _make_cache_key(cache_prefix, cache_args, kwargs)

            try:
                redis = get_redis_client()
                cached_value = redis.get(cache_key)
                if cached_value is not None:
                    return json.loads(cached_value)
            except Exception:
                # Se Redis falhar, executa a funcao normalmente
                logger.debug('Cache miss (Redis indisponivel) para %s', cache_key)

            # Executa funcao original
            result = func(*args, **kwargs)

            # Armazena no cache
            try:
                redis = get_redis_client()
                serialized = json.dumps(result, default=_json_serializer)
                redis.setex(cache_key, ttl, serialized)
            except Exception:
                logger.debug('Falha ao salvar cache para %s', cache_key)

            return result
        # Expoe o prefixo para invalidacao
        wrapper._cache_prefix = prefix or f'{func.__module__}.{func.__qualname__}'
        return wrapper
    return decorator


def invalidate_cache(prefix: str) -> int:
    """
    Invalida todas as chaves de cache que correspondem ao prefixo.

    Args:
        prefix: Prefixo das chaves a invalidar (ex: 'dashboard:summary').

    Returns:
        Numero de chaves removidas.
    """
    try:
        redis = get_redis_client()
        pattern = f'{_CACHE_PREFIX}{prefix}:*'
        keys = list(redis.scan_iter(match=pattern, count=100))
        if keys:
            deleted = redis.delete(*keys)
            logger.debug('Cache invalidado: %d chaves com prefixo "%s"', deleted, prefix)
            return deleted
        return 0
    except Exception:
        logger.debug('Falha ao invalidar cache com prefixo "%s"', prefix)
        return 0


def invalidate_all_cache() -> int:
    """Remove todas as chaves de cache."""
    try:
        redis = get_redis_client()
        pattern = f'{_CACHE_PREFIX}*'
        keys = list(redis.scan_iter(match=pattern, count=500))
        if keys:
            return redis.delete(*keys)
        return 0
    except Exception:
        return 0


def _json_serializer(obj: Any) -> Any:
    """Serializer customizado para JSON que suporta tipos comuns."""
    import uuid
    from datetime import date, datetime

    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, date):
        return obj.isoformat()
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if hasattr(obj, 'model_dump'):
        return obj.model_dump()
    if hasattr(obj, '__dict__'):
        return obj.__dict__
    raise TypeError(f'Tipo nao serializavel: {type(obj)}')
