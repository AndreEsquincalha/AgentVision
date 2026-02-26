"""
Logging estruturado centralizado para o AgentVision.

Configura structlog com processadores para JSON output, request_id,
correlation_id e log levels por modulo. Compativel com logging stdlib
para que bibliotecas terceiras tambem emitam JSON.
"""

import logging
import logging.config
import uuid
from contextvars import ContextVar

import structlog

# ---------------------------------------------------------------------------
# Context variables — propagadas automaticamente em chamadas async/sync
# ---------------------------------------------------------------------------
request_id_var: ContextVar[str | None] = ContextVar('request_id', default=None)
correlation_id_var: ContextVar[str | None] = ContextVar('correlation_id', default=None)
user_id_var: ContextVar[str | None] = ContextVar('user_id', default=None)


def generate_id() -> str:
    """Gera UUID4 curto (primeiros 8 chars) para legibilidade."""
    return uuid.uuid4().hex[:12]


# ---------------------------------------------------------------------------
# Structlog processors
# ---------------------------------------------------------------------------

def add_request_context(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict,
) -> dict:
    """Adiciona request_id, correlation_id e user_id ao evento de log."""
    req_id = request_id_var.get()
    corr_id = correlation_id_var.get()
    uid = user_id_var.get()
    if req_id:
        event_dict['request_id'] = req_id
    if corr_id:
        event_dict['correlation_id'] = corr_id
    if uid:
        event_dict['user_id'] = uid
    return event_dict


def add_service_name(
    logger: logging.Logger,
    method_name: str,
    event_dict: dict,
) -> dict:
    """Adiciona nome do servico ao evento de log."""
    event_dict['service'] = 'agentvision'
    return event_dict


# ---------------------------------------------------------------------------
# Configuracao global de log levels
# ---------------------------------------------------------------------------
_runtime_log_levels: dict[str, str] = {}


def parse_log_levels(log_levels_str: str) -> dict[str, str]:
    """
    Parseia string de log levels por modulo.

    Formato: "app.modules.agents:DEBUG,app.modules.jobs:INFO"
    """
    levels: dict[str, str] = {}
    if not log_levels_str or not log_levels_str.strip():
        return levels
    for pair in log_levels_str.split(','):
        pair = pair.strip()
        if ':' not in pair:
            continue
        module, level = pair.rsplit(':', 1)
        module = module.strip()
        level = level.strip().upper()
        if level in ('DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'):
            levels[module] = level
    return levels


def set_module_log_levels(levels: dict[str, str]) -> None:
    """Aplica log levels por modulo no logging stdlib."""
    for module_name, level_str in levels.items():
        module_logger = logging.getLogger(module_name)
        module_logger.setLevel(getattr(logging, level_str))


def update_runtime_log_levels(levels: dict[str, str]) -> None:
    """Atualiza log levels em runtime (via endpoint admin)."""
    _runtime_log_levels.update(levels)
    set_module_log_levels(levels)


def get_current_log_levels() -> dict[str, str]:
    """Retorna os log levels atualmente configurados."""
    return dict(_runtime_log_levels)


# ---------------------------------------------------------------------------
# Setup principal
# ---------------------------------------------------------------------------

_configured = False


def setup_logging(
    log_level: str = 'INFO',
    log_format: str = 'json',
    log_levels: str = '',
) -> None:
    """
    Configura logging estruturado para toda a aplicacao.

    Deve ser chamado uma unica vez no startup (main.py e celery_app.py).

    Args:
        log_level: Nivel de log global (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_format: Formato de saida ('json' ou 'console').
        log_levels: Overrides por modulo (ex: "app.modules.agents:DEBUG").
    """
    global _configured
    if _configured:
        return
    _configured = True

    log_level = log_level.upper()

    # Processors compartilhados entre structlog e stdlib
    shared_processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.filter_by_level,
        add_service_name,
        add_request_context,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt='iso'),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if log_format == 'console':
        renderer = structlog.dev.ConsoleRenderer()
    else:
        renderer = structlog.processors.JSONRenderer(ensure_ascii=False)

    # Configuracao do logging stdlib para capturar logs de libs terceiras
    logging.config.dictConfig({
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'structlog': {
                '()': structlog.stdlib.ProcessorFormatter,
                'processors': [
                    structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    renderer,
                ],
                'foreign_pre_chain': shared_processors,
            },
        },
        'handlers': {
            'default': {
                'class': 'logging.StreamHandler',
                'formatter': 'structlog',
                'stream': 'ext://sys.stdout',
            },
        },
        'root': {
            'handlers': ['default'],
            'level': log_level,
        },
        'loggers': {
            # Reduzir ruido de libs terceiras
            'uvicorn': {'level': 'WARNING'},
            'uvicorn.access': {'level': 'WARNING'},
            'celery': {'level': 'INFO'},
            'sqlalchemy.engine': {'level': 'WARNING'},
            'httpx': {'level': 'WARNING'},
            'httpcore': {'level': 'WARNING'},
        },
    })

    # Configuracao do structlog
    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Aplicar log levels por modulo
    module_levels = parse_log_levels(log_levels)
    if module_levels:
        _runtime_log_levels.update(module_levels)
        set_module_log_levels(module_levels)


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Retorna um logger structlog com o nome do modulo.

    Uso:
        logger = get_logger(__name__)
        logger.info('mensagem', extra_field='valor')
    """
    return structlog.get_logger(name)
