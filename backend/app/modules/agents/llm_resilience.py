"""
Modulo de resiliencia para chamadas LLM.

Contem:
- Decorator @retry_with_backoff: retry com exponential backoff e jitter (13.1.1)
- LLMCircuitBreaker: circuit breaker por provider com estado em Redis (13.1.3)
- LLMFallbackChain: fallback automatico entre providers (13.1.2)
"""

import json
import logging
import random
import time
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable

logger = logging.getLogger(__name__)

# -------------------------------------------------------------------------
# Classificacao de erros transientes vs permanentes
# -------------------------------------------------------------------------

# Codigos HTTP de erros transientes (retry vale a pena)
_TRANSIENT_STATUS_CODES = {429, 500, 502, 503, 504}

# Codigos HTTP de erros permanentes (retry nao resolve)
_PERMANENT_STATUS_CODES = {400, 401, 403, 404, 422}

# Strings que indicam erro transiente na mensagem
_TRANSIENT_ERROR_KEYWORDS = (
    'rate limit',
    'rate_limit',
    'too many requests',
    'server error',
    'internal server error',
    'service unavailable',
    'bad gateway',
    'gateway timeout',
    'timeout',
    'timed out',
    'connection',
    'connect',
    'overloaded',
    'capacity',
    'temporarily',
)

# Strings que indicam erro permanente na mensagem
_PERMANENT_ERROR_KEYWORDS = (
    'unauthorized',
    'invalid api key',
    'invalid_api_key',
    'authentication',
    'permission',
    'forbidden',
    'not found',
    'bad request',
    'invalid request',
    'billing',
    'quota exceeded',
)


def _is_transient_error(error: Exception) -> bool:
    """
    Determina se um erro e transiente (vale fazer retry).

    Verifica status code HTTP (se disponivel) e palavras-chave na mensagem.
    """
    error_str = str(error).lower()

    # Verifica se e erro permanente primeiro (prioridade)
    for keyword in _PERMANENT_ERROR_KEYWORDS:
        if keyword in error_str:
            return False

    # Verifica status code se disponivel no erro
    status_code = getattr(error, 'status_code', None)
    if status_code is None:
        # Tenta extrair de atributos comuns dos SDKs
        response = getattr(error, 'response', None)
        if response is not None:
            status_code = getattr(response, 'status_code', None)

    if status_code is not None:
        if status_code in _PERMANENT_STATUS_CODES:
            return False
        if status_code in _TRANSIENT_STATUS_CODES:
            return True

    # Verifica palavras-chave de erro transiente
    for keyword in _TRANSIENT_ERROR_KEYWORDS:
        if keyword in error_str:
            return True

    # Erros de conexao e timeout sao sempre transientes
    import httpx
    if isinstance(error, (TimeoutError, ConnectionError, OSError)):
        return True
    if isinstance(error, (httpx.ConnectError, httpx.TimeoutException)):
        return True

    # Default: considera transiente para nao perder chamadas que poderiam funcionar
    return True


# -------------------------------------------------------------------------
# 13.1.1 — Retry com exponential backoff e jitter
# -------------------------------------------------------------------------

def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    jitter: bool = True,
) -> Callable:
    """
    Decorator que adiciona retry com exponential backoff e jitter.

    Aplica-se a metodos que fazem chamadas a APIs de LLM. Faz retry
    apenas para erros transientes (429, 500, timeout, conexao).
    Nao faz retry para erros permanentes (401, 400, 404).

    Args:
        max_retries: Numero maximo de tentativas alem da primeira.
        base_delay: Delay base em segundos (dobra a cada tentativa).
        max_delay: Delay maximo em segundos.
        jitter: Se True, adiciona jitter aleatorio para evitar thundering herd.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None

            for attempt in range(max_retries + 1):
                try:
                    result = func(*args, **kwargs)

                    # Verifica se o resultado indica erro (AnalysisResult com texto de erro)
                    # Se tokens_used == 0 e texto comeca com 'Erro', pode ser erro tratado
                    # Neste caso, confiamos que o provider ja lidou com o erro internamente
                    return result

                except Exception as e:
                    last_exception = e

                    # Se e erro permanente, nao faz retry
                    if not _is_transient_error(e):
                        logger.warning(
                            'retry_with_backoff: erro permanente em %s '
                            '(tentativa %d/%d, sem retry) — %s',
                            func.__name__,
                            attempt + 1,
                            max_retries + 1,
                            str(e),
                        )
                        raise

                    # Se ja esgotou tentativas, levanta a excecao
                    if attempt >= max_retries:
                        logger.error(
                            'retry_with_backoff: todas as %d tentativas falharam '
                            'para %s — %s',
                            max_retries + 1,
                            func.__name__,
                            str(e),
                        )
                        raise

                    # Calcula delay com exponential backoff
                    delay = min(base_delay * (2 ** attempt), max_delay)

                    # Adiciona jitter aleatorio (0.5x a 1.5x)
                    if jitter:
                        delay = delay * (0.5 + random.random())

                    logger.warning(
                        'retry_with_backoff: erro transiente em %s '
                        '(tentativa %d/%d, retrying em %.1fs) — %s',
                        func.__name__,
                        attempt + 1,
                        max_retries + 1,
                        delay,
                        str(e),
                    )

                    time.sleep(delay)

            # Nunca deveria chegar aqui, mas por seguranca
            if last_exception:
                raise last_exception

        return wrapper
    return decorator


# -------------------------------------------------------------------------
# 13.1.3 — Circuit Breaker para APIs de LLM
# -------------------------------------------------------------------------

@dataclass
class CircuitBreakerState:
    """Estado do circuit breaker."""
    state: str  # 'closed', 'open', 'half_open'
    failure_count: int
    last_failure_time: float  # timestamp
    last_success_time: float  # timestamp


class LLMCircuitBreaker:
    """
    Circuit breaker para APIs de LLM com estado persistido em Redis.

    Estados:
    - closed: funcionando normalmente, contando falhas consecutivas
    - open: provider indisponivel, pula direto para fallback
    - half_open: testando com 1 chamada para ver se voltou

    Transicoes:
    - closed -> open: apos N falhas consecutivas
    - open -> half_open: apos cooldown
    - half_open -> closed: se teste funcionar
    - half_open -> open: se teste falhar
    """

    # Prefixo para chaves Redis
    _REDIS_PREFIX = 'llm_circuit_breaker'

    def __init__(
        self,
        failure_threshold: int = 5,
        cooldown_seconds: int = 300,
    ) -> None:
        """
        Args:
            failure_threshold: Falhas consecutivas para abrir o circuito.
            cooldown_seconds: Segundos antes de tentar half-open.
        """
        self._failure_threshold = failure_threshold
        self._cooldown_seconds = cooldown_seconds

    def _get_redis_key(self, provider_name: str) -> str:
        """Retorna a chave Redis para o estado do circuit breaker."""
        return f'{self._REDIS_PREFIX}:{provider_name}'

    def _get_redis(self):
        """Retorna cliente Redis."""
        from app.shared.redis_client import get_redis_client
        return get_redis_client()

    def get_state(self, provider_name: str) -> CircuitBreakerState:
        """
        Obtem o estado atual do circuit breaker para um provider.

        Args:
            provider_name: Nome do provider (anthropic, openai, google, ollama).

        Returns:
            Estado atual do circuit breaker.
        """
        try:
            redis = self._get_redis()
            key = self._get_redis_key(provider_name)
            data = redis.get(key)

            if not data:
                return CircuitBreakerState(
                    state='closed',
                    failure_count=0,
                    last_failure_time=0.0,
                    last_success_time=0.0,
                )

            parsed = json.loads(data)
            state = CircuitBreakerState(
                state=parsed.get('state', 'closed'),
                failure_count=parsed.get('failure_count', 0),
                last_failure_time=parsed.get('last_failure_time', 0.0),
                last_success_time=parsed.get('last_success_time', 0.0),
            )

            # Verifica transicao open -> half_open (cooldown expirou)
            if state.state == 'open':
                elapsed = time.time() - state.last_failure_time
                if elapsed >= self._cooldown_seconds:
                    state.state = 'half_open'
                    self._save_state(provider_name, state)
                    logger.info(
                        'CircuitBreaker [%s]: open -> half_open '
                        '(cooldown de %ds expirou)',
                        provider_name, self._cooldown_seconds,
                    )

            return state

        except Exception as e:
            logger.debug(
                'CircuitBreaker: erro ao obter estado para %s — %s',
                provider_name, str(e),
            )
            # Se Redis falhar, considera circuito fechado (fail-open)
            return CircuitBreakerState(
                state='closed',
                failure_count=0,
                last_failure_time=0.0,
                last_success_time=0.0,
            )

    def _save_state(
        self,
        provider_name: str,
        state: CircuitBreakerState,
    ) -> None:
        """Persiste o estado do circuit breaker no Redis."""
        try:
            redis = self._get_redis()
            key = self._get_redis_key(provider_name)
            data = json.dumps({
                'state': state.state,
                'failure_count': state.failure_count,
                'last_failure_time': state.last_failure_time,
                'last_success_time': state.last_success_time,
            })
            # TTL de 1 hora para auto-limpeza de estados antigos
            redis.setex(key, 3600, data)
        except Exception as e:
            logger.debug(
                'CircuitBreaker: erro ao salvar estado para %s — %s',
                provider_name, str(e),
            )

    def is_available(self, provider_name: str) -> bool:
        """
        Verifica se o provider esta disponivel (circuito nao esta aberto).

        Args:
            provider_name: Nome do provider.

        Returns:
            True se o circuito esta fechado ou half-open, False se aberto.
        """
        state = self.get_state(provider_name)
        return state.state != 'open'

    def record_success(self, provider_name: str) -> None:
        """
        Registra uma chamada bem-sucedida.

        Se half_open -> fechado, se closed -> reseta contagem de falhas.
        """
        state = self.get_state(provider_name)
        old_state = state.state

        state.state = 'closed'
        state.failure_count = 0
        state.last_success_time = time.time()
        self._save_state(provider_name, state)

        if old_state == 'half_open':
            logger.info(
                'CircuitBreaker [%s]: half_open -> closed (teste bem-sucedido)',
                provider_name,
            )

    def record_failure(self, provider_name: str) -> None:
        """
        Registra uma falha.

        Se half_open -> abre novamente. Se closed e excedeu threshold -> abre.
        """
        state = self.get_state(provider_name)
        state.failure_count += 1
        state.last_failure_time = time.time()

        if state.state == 'half_open':
            # Teste falhou, volta para open
            state.state = 'open'
            logger.warning(
                'CircuitBreaker [%s]: half_open -> open '
                '(teste falhou, cooldown de %ds)',
                provider_name, self._cooldown_seconds,
            )
        elif state.failure_count >= self._failure_threshold:
            state.state = 'open'
            logger.warning(
                'CircuitBreaker [%s]: closed -> open '
                '(%d falhas consecutivas >= threshold %d)',
                provider_name, state.failure_count, self._failure_threshold,
            )

        self._save_state(provider_name, state)

    def reset(self, provider_name: str) -> None:
        """Reseta o circuit breaker para o estado inicial (closed)."""
        state = CircuitBreakerState(
            state='closed',
            failure_count=0,
            last_failure_time=0.0,
            last_success_time=time.time(),
        )
        self._save_state(provider_name, state)
        logger.info('CircuitBreaker [%s]: resetado para closed', provider_name)

    def get_all_states(self) -> dict[str, CircuitBreakerState]:
        """
        Retorna o estado de todos os providers conhecidos.

        Returns:
            Dict provider_name -> CircuitBreakerState.
        """
        providers = ['anthropic', 'openai', 'google', 'ollama']
        return {p: self.get_state(p) for p in providers}


# Instancia global do circuit breaker
circuit_breaker = LLMCircuitBreaker()


# -------------------------------------------------------------------------
# 13.1.2 — Fallback automatico entre providers
# -------------------------------------------------------------------------

class LLMFallbackChain:
    """
    Executa chamadas LLM com fallback automatico entre providers.

    Se o provider primario falhar apos retries, tenta o proximo na lista
    de fallback. Integra com circuit breaker para pular providers indisponiveis.
    """

    def __init__(
        self,
        primary_config: dict,
        fallback_configs: list[dict] | None = None,
    ) -> None:
        """
        Args:
            primary_config: Config do provider primario
                            (provider, api_key, model, temperature, max_tokens, timeout).
            fallback_configs: Lista de configs de providers de fallback.
                              Cada dict tem as mesmas chaves do primary_config.
        """
        self._primary_config = primary_config
        self._fallback_configs = fallback_configs or []
        self._cb = circuit_breaker
        self._actual_provider_used: str | None = None

    @property
    def actual_provider_used(self) -> str | None:
        """Retorna o nome do provider que realmente atendeu a chamada."""
        return self._actual_provider_used

    def execute(
        self,
        call_fn: Callable,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Executa uma funcao com fallback entre providers.

        Args:
            call_fn: Funcao que recebe um provider e executa a chamada.
                     Signature: call_fn(provider, *args, **kwargs)
            *args: Argumentos posicionais para call_fn.
            **kwargs: Argumentos nomeados para call_fn.

        Returns:
            Resultado da chamada bem-sucedida.

        Raises:
            Exception: Se todos os providers falharem.
        """
        from app.modules.agents.llm_provider import get_llm_provider

        all_configs = [self._primary_config] + self._fallback_configs
        last_error: Exception | None = None

        for i, config in enumerate(all_configs):
            provider_name = config.get('provider', 'unknown')
            is_primary = (i == 0)

            # Verifica circuit breaker
            if not self._cb.is_available(provider_name):
                logger.warning(
                    'LLMFallbackChain: pulando provider %s '
                    '(circuit breaker aberto)',
                    provider_name,
                )
                continue

            try:
                provider = get_llm_provider(
                    provider_name=provider_name,
                    api_key=config.get('api_key', ''),
                    model=config.get('model', ''),
                    temperature=config.get('temperature', 0.7),
                    max_tokens=config.get('max_tokens', 4096),
                    timeout=config.get('timeout', 120),
                )

                if not is_primary:
                    logger.info(
                        'LLMFallbackChain: provider %s falhou, '
                        'tentando fallback %s',
                        all_configs[0].get('provider', 'unknown'),
                        provider_name,
                    )

                result = call_fn(provider, *args, **kwargs)

                # Registra sucesso no circuit breaker
                self._cb.record_success(provider_name)
                self._actual_provider_used = provider_name

                if not is_primary:
                    logger.info(
                        'LLMFallbackChain: fallback %s bem-sucedido',
                        provider_name,
                    )

                return result

            except Exception as e:
                last_error = e
                self._cb.record_failure(provider_name)
                logger.warning(
                    'LLMFallbackChain: provider %s falhou — %s',
                    provider_name, str(e),
                )
                continue

        # Todos os providers falharam
        error_msg = (
            f'Todos os providers LLM falharam. '
            f'Ultimo erro: {str(last_error)}'
        )
        logger.error('LLMFallbackChain: %s', error_msg)
        if last_error:
            raise last_error
        raise RuntimeError(error_msg)


# -------------------------------------------------------------------------
# 13.1.4 — Health check para providers LLM
# -------------------------------------------------------------------------

@dataclass
class ProviderHealthStatus:
    """Status de saude de um provider LLM."""
    provider: str
    status: str  # 'online', 'degraded', 'offline'
    latency_ms: float
    last_check: float  # timestamp
    error: str | None = None


_HEALTH_CHECK_REDIS_PREFIX = 'llm_health'
_HEALTH_CHECK_TTL = 900  # 15 minutos


def check_provider_health(
    provider_name: str,
    api_key: str,
    model: str,
) -> ProviderHealthStatus:
    """
    Testa a saude de um provider LLM com um prompt minimo.

    Args:
        provider_name: Nome do provider.
        api_key: Chave de API.
        model: Nome do modelo.

    Returns:
        ProviderHealthStatus com latencia e status.
    """
    from app.modules.agents.llm_provider import get_llm_provider

    start = time.time()
    try:
        provider = get_llm_provider(
            provider_name=provider_name,
            api_key=api_key,
            model=model,
            temperature=0.0,
            max_tokens=50,
            timeout=15,
        )

        # Prompt minimo para testar conectividade
        # Usa analyze_image com imagem 1x1 transparente minima
        # Para providers que exigem imagem, cria PNG minimo
        import struct
        import zlib

        # PNG 1x1 pixel transparente (minimo valido)
        def _make_1x1_png() -> bytes:
            signature = b'\x89PNG\r\n\x1a\n'
            # IHDR
            ihdr_data = struct.pack('>IIBBBBB', 1, 1, 8, 2, 0, 0, 0)
            ihdr_crc = zlib.crc32(b'IHDR' + ihdr_data) & 0xFFFFFFFF
            ihdr = struct.pack('>I', 13) + b'IHDR' + ihdr_data + struct.pack('>I', ihdr_crc)
            # IDAT
            raw_data = zlib.compress(b'\x00\xff\xff\xff')
            idat_crc = zlib.crc32(b'IDAT' + raw_data) & 0xFFFFFFFF
            idat = struct.pack('>I', len(raw_data)) + b'IDAT' + raw_data + struct.pack('>I', idat_crc)
            # IEND
            iend_crc = zlib.crc32(b'IEND') & 0xFFFFFFFF
            iend = struct.pack('>I', 0) + b'IEND' + struct.pack('>I', iend_crc)
            return signature + ihdr + idat + iend

        tiny_image = _make_1x1_png()
        result = provider.analyze_image(tiny_image, 'Respond with OK')

        elapsed_ms = (time.time() - start) * 1000

        # Se retornou resultado com tokens > 0, esta online
        if result.tokens_used > 0:
            status = 'online'
        elif result.text and 'Erro' not in result.text:
            status = 'online'
        else:
            status = 'degraded'

        return ProviderHealthStatus(
            provider=provider_name,
            status=status,
            latency_ms=round(elapsed_ms, 1),
            last_check=time.time(),
            error=None if status == 'online' else result.text,
        )

    except Exception as e:
        elapsed_ms = (time.time() - start) * 1000
        return ProviderHealthStatus(
            provider=provider_name,
            status='offline',
            latency_ms=round(elapsed_ms, 1),
            last_check=time.time(),
            error=str(e),
        )


def save_health_status(status: ProviderHealthStatus) -> None:
    """Salva status de saude no Redis."""
    try:
        from app.shared.redis_client import get_redis_client
        redis = get_redis_client()
        key = f'{_HEALTH_CHECK_REDIS_PREFIX}:{status.provider}'
        data = json.dumps({
            'provider': status.provider,
            'status': status.status,
            'latency_ms': status.latency_ms,
            'last_check': status.last_check,
            'error': status.error,
        })
        redis.setex(key, _HEALTH_CHECK_TTL, data)
    except Exception as e:
        logger.debug('Erro ao salvar health status: %s', str(e))


def get_health_status(provider_name: str) -> ProviderHealthStatus | None:
    """Busca status de saude do Redis."""
    try:
        from app.shared.redis_client import get_redis_client
        redis = get_redis_client()
        key = f'{_HEALTH_CHECK_REDIS_PREFIX}:{provider_name}'
        data = redis.get(key)
        if not data:
            return None
        parsed = json.loads(data)
        return ProviderHealthStatus(
            provider=parsed['provider'],
            status=parsed['status'],
            latency_ms=parsed['latency_ms'],
            last_check=parsed['last_check'],
            error=parsed.get('error'),
        )
    except Exception as e:
        logger.debug('Erro ao buscar health status: %s', str(e))
        return None


def get_all_health_statuses() -> list[dict]:
    """
    Retorna status de saude de todos os providers.

    Returns:
        Lista de dicts com status de cada provider.
    """
    providers = ['anthropic', 'openai', 'google', 'ollama']
    statuses = []
    for provider in providers:
        status = get_health_status(provider)
        if status:
            statuses.append({
                'provider': status.provider,
                'status': status.status,
                'latency_ms': status.latency_ms,
                'last_check': status.last_check,
                'error': status.error,
            })
        else:
            statuses.append({
                'provider': provider,
                'status': 'unknown',
                'latency_ms': 0,
                'last_check': 0,
                'error': 'Nenhum health check registrado',
            })
    return statuses
