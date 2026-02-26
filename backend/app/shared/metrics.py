"""
Metricas Prometheus customizadas para o AgentVision.

Define contadores, histogramas e gauges para monitorar execucoes,
tokens LLM, screenshots e estado dos workers.
"""

from prometheus_client import Counter, Gauge, Histogram

# ---------------------------------------------------------------------------
# Metricas de execucoes
# ---------------------------------------------------------------------------

EXECUTIONS_TOTAL = Counter(
    'agentvision_executions_total',
    'Total de execucoes por status',
    ['status', 'job_id'],
)

EXECUTION_DURATION_SECONDS = Histogram(
    'agentvision_execution_duration_seconds',
    'Duracao das execucoes em segundos',
    buckets=[10, 30, 60, 120, 300, 600, 1200, 1800, 3600],
)

ACTIVE_EXECUTIONS = Gauge(
    'agentvision_active_executions',
    'Numero de execucoes em andamento',
)

# ---------------------------------------------------------------------------
# Metricas de LLM / tokens
# ---------------------------------------------------------------------------

LLM_TOKENS_TOTAL = Counter(
    'agentvision_llm_tokens_total',
    'Total de tokens consumidos por provider e modelo',
    ['provider', 'model', 'direction'],  # direction: input/output
)

LLM_REQUESTS_TOTAL = Counter(
    'agentvision_llm_requests_total',
    'Total de requests para providers LLM',
    ['provider', 'status'],  # status: success/error
)

LLM_REQUEST_DURATION_SECONDS = Histogram(
    'agentvision_llm_request_duration_seconds',
    'Duracao das chamadas ao LLM em segundos',
    ['provider'],
    buckets=[1, 2, 5, 10, 20, 30, 60, 120],
)

# ---------------------------------------------------------------------------
# Metricas de screenshots
# ---------------------------------------------------------------------------

SCREENSHOTS_CAPTURED_TOTAL = Counter(
    'agentvision_screenshots_captured_total',
    'Total de screenshots capturados',
)

# ---------------------------------------------------------------------------
# Metricas de delivery
# ---------------------------------------------------------------------------

DELIVERIES_TOTAL = Counter(
    'agentvision_deliveries_total',
    'Total de entregas por canal e status',
    ['channel', 'status'],  # status: success/failed
)

# ---------------------------------------------------------------------------
# Helpers para instrumentar o codigo existente
# ---------------------------------------------------------------------------


def track_execution_started(job_id: str) -> None:
    """Registra inicio de uma execucao."""
    ACTIVE_EXECUTIONS.inc()


def track_execution_finished(job_id: str, status: str, duration_seconds: float) -> None:
    """Registra finalizacao de uma execucao."""
    EXECUTIONS_TOTAL.labels(status=status, job_id=job_id).inc()
    EXECUTION_DURATION_SECONDS.observe(duration_seconds)
    ACTIVE_EXECUTIONS.dec()


def track_llm_tokens(
    provider: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
) -> None:
    """Registra consumo de tokens LLM."""
    LLM_TOKENS_TOTAL.labels(provider=provider, model=model, direction='input').inc(input_tokens)
    LLM_TOKENS_TOTAL.labels(provider=provider, model=model, direction='output').inc(output_tokens)


def track_llm_request(provider: str, status: str, duration: float) -> None:
    """Registra uma chamada ao LLM."""
    LLM_REQUESTS_TOTAL.labels(provider=provider, status=status).inc()
    LLM_REQUEST_DURATION_SECONDS.labels(provider=provider).observe(duration)


def track_screenshot_captured(count: int = 1) -> None:
    """Registra captura de screenshots."""
    SCREENSHOTS_CAPTURED_TOTAL.inc(count)


def track_delivery(channel: str, status: str) -> None:
    """Registra entrega por canal."""
    DELIVERIES_TOTAL.labels(channel=channel, status=status).inc()
