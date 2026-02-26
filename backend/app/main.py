import re
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.database import SessionLocal
from app.shared.exceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
)
from app.shared.logging import (
    correlation_id_var,
    generate_id,
    get_logger,
    request_id_var,
    setup_logging,
    user_id_var,
)
from app.modules.audit.repository import AuditLogRepository
from app.modules.audit.service import AuditLogService
from app.modules.auth.service import decode_token

# Inicializa logging estruturado antes de qualquer outro codigo
setup_logging(
    log_level=settings.log_level,
    log_format=settings.log_format,
    log_levels=settings.log_levels,
)

logger = get_logger(__name__)

# Limites e headers de seguranca
_MAX_BODY_SIZE_BYTES = 10 * 1024 * 1024
_SECURITY_HEADERS = {
    'X-Content-Type-Options': 'nosniff',
    'X-Frame-Options': 'DENY',
    'Content-Security-Policy': "default-src 'self'",
    'Referrer-Policy': 'strict-origin-when-cross-origin',
    'Permissions-Policy': 'camera=(), microphone=(), geolocation=()',
    'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
}

_UUID_RE = re.compile(
    r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-'
    r'[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$'
)


def _extract_resource(path: str) -> tuple[str | None, str | None]:
    """Extrai resource_type e resource_id da URL."""
    parts = path.strip('/').split('/')
    if len(parts) < 2 or parts[0] != 'api':
        return None, None
    resource_type = parts[1]
    resource_id = parts[2] if len(parts) > 2 else None
    if resource_id and not _UUID_RE.match(resource_id):
        return resource_type, resource_id
    return resource_type, resource_id


def _get_user_id_from_request(request: Request) -> str | None:
    """Extrai user_id do token JWT (se presente)."""
    auth_header = request.headers.get('authorization', '')
    if not auth_header.lower().startswith('bearer '):
        return None
    token = auth_header.split(' ', 1)[1]
    try:
        payload = decode_token(token)
        return payload.get('sub')
    except Exception:
        return None


def _get_request_ip(request: Request) -> str | None:
    """Obtencao de IP do cliente com suporte a proxy."""
    forwarded = request.headers.get('x-forwarded-for')
    if forwarded:
        return forwarded.split(',')[0].strip()
    if request.client:
        return request.client.host
    return None

# Valores padrao inseguros que devem ser alterados em producao
_INSECURE_DEFAULTS: dict[str, str] = {
    'jwt_secret_key': 'change-me-to-a-long-random-secret-key',
    'encryption_key': 'change-me-to-a-valid-fernet-key',
    'admin_password': 'admin123',
}


def _check_security_settings() -> None:
    """
    Verifica configuracoes de seguranca no startup.

    Emite avisos se valores padrao inseguros estiverem em uso,
    mas nao bloqueia a inicializacao para permitir desenvolvimento local.
    """
    for setting_name, insecure_value in _INSECURE_DEFAULTS.items():
        current_value = getattr(settings, setting_name, None)
        if current_value == insecure_value:
            logger.warning(
                'AVISO DE SEGURANCA: A configuracao "%s" esta usando o valor padrao. '
                'Altere para um valor seguro no arquivo .env antes de usar em producao.',
                setting_name.upper(),
            )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Gerencia o ciclo de vida da aplicacao (startup/shutdown)."""
    # Startup: verifica configuracoes de seguranca
    _check_security_settings()
    logger.info(
        'AgentVision API v1.0.0 iniciada. CORS origens: %s',
        settings.cors_origins,
    )
    yield
    # Shutdown: limpeza de recursos
    logger.info('AgentVision API encerrada.')


app = FastAPI(
    title='AgentVision API',
    description='API da plataforma AgentVision - Automacao com agentes de IA',
    version='1.0.0',
    lifespan=lifespan,
    docs_url='/docs',
    redoc_url='/redoc',
)

# -------------------------------------------------------------------------
# CORS Middleware
# -------------------------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'],
    allow_headers=[
        'Authorization',
        'Content-Type',
        'Accept',
        'Origin',
        'X-Requested-With',
    ],
    expose_headers=['Content-Disposition'],
)

# -------------------------------------------------------------------------
# Prometheus Instrumentation
# -------------------------------------------------------------------------
from prometheus_fastapi_instrumentator import Instrumentator

Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    should_group_untemplated=True,
    excluded_handlers=['/metrics', '/docs', '/redoc', '/openapi.json'],
).instrument(app).expose(app, endpoint='/metrics', include_in_schema=False)


@app.middleware('http')
async def request_context_middleware(
    request: Request,
    call_next,
) -> JSONResponse:
    """
    Gera request_id e correlation_id para cada request HTTP.

    O correlation_id pode ser propagado pelo cliente via header
    X-Correlation-ID, ou sera gerado automaticamente.
    O request_id e sempre gerado pelo servidor.
    """
    req_id = generate_id()
    corr_id = request.headers.get('x-correlation-id') or generate_id()

    # Setar context vars para propagacao automatica
    req_token = request_id_var.set(req_id)
    corr_token = correlation_id_var.set(corr_id)

    # Extrair user_id do token JWT se presente
    uid = _get_user_id_from_request(request)
    uid_token = user_id_var.set(uid)

    try:
        response = await call_next(request)
        # Incluir IDs nos headers de resposta para rastreamento
        response.headers['X-Request-ID'] = req_id
        response.headers['X-Correlation-ID'] = corr_id
        return response
    finally:
        request_id_var.reset(req_token)
        correlation_id_var.reset(corr_token)
        user_id_var.reset(uid_token)


@app.middleware('http')
async def request_size_limit_middleware(
    request: Request,
    call_next,
) -> JSONResponse:
    """Limita tamanho maximo do payload."""
    body = await request.body()
    if len(body) > _MAX_BODY_SIZE_BYTES:
        return JSONResponse(
            status_code=413,
            content={
                'success': False,
                'message': 'Payload muito grande. Limite: 10MB.',
            },
        )
    request._body = body
    return await call_next(request)


@app.middleware('http')
async def security_headers_middleware(request: Request, call_next) -> JSONResponse:
    """Aplica headers de seguranca."""
    response = await call_next(request)
    for key, value in _SECURITY_HEADERS.items():
        response.headers.setdefault(key, value)
    return response


@app.middleware('http')
async def audit_log_middleware(request: Request, call_next) -> JSONResponse:
    """Registra logs de auditoria automaticamente."""
    response = await call_next(request)

    if request.method not in {'POST', 'PUT', 'PATCH', 'DELETE'}:
        return response

    if not request.url.path.startswith('/api/'):
        return response

    # Auth é tratado no proprio router
    if request.url.path.startswith('/api/auth'):
        return response

    if response.status_code >= 400:
        return response

    resource_type, resource_id = _extract_resource(request.url.path)
    if not resource_type:
        return response

    action_map = {
        'POST': 'create',
        'PUT': 'update',
        'PATCH': 'update',
        'DELETE': 'delete',
    }
    action = action_map.get(request.method, request.method.lower())
    user_id = _get_user_id_from_request(request)
    parsed_user_id = None
    if user_id and _UUID_RE.match(user_id):
        from uuid import UUID
        parsed_user_id = UUID(user_id)

    db = SessionLocal()
    try:
        service = AuditLogService(AuditLogRepository(db))
        service.create_log(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=parsed_user_id,
            ip_address=_get_request_ip(request),
            details={
                'path': request.url.path,
                'method': request.method,
                'status_code': response.status_code,
            },
        )
    except Exception:
        pass
    finally:
        db.close()

    return response

# -------------------------------------------------------------------------
# Handlers globais de excecoes
# -------------------------------------------------------------------------


@app.exception_handler(NotFoundException)
async def not_found_exception_handler(
    request: Request, exc: NotFoundException
) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={'success': False, 'message': str(exc)},
    )


@app.exception_handler(UnauthorizedException)
async def unauthorized_exception_handler(
    request: Request, exc: UnauthorizedException
) -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={'success': False, 'message': str(exc)},
    )


@app.exception_handler(ForbiddenException)
async def forbidden_exception_handler(
    request: Request, exc: ForbiddenException
) -> JSONResponse:
    return JSONResponse(
        status_code=403,
        content={'success': False, 'message': str(exc)},
    )


@app.exception_handler(BadRequestException)
async def bad_request_exception_handler(
    request: Request, exc: BadRequestException
) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={'success': False, 'message': str(exc)},
    )


# -------------------------------------------------------------------------
# Routers dos modulos
# -------------------------------------------------------------------------
from app.modules.auth.router import router as auth_router
from app.modules.dashboard.router import router as dashboard_router
from app.modules.delivery.router import router as delivery_router
from app.modules.executions.router import router as executions_router
from app.modules.jobs.router import router as jobs_router
from app.modules.projects.router import router as projects_router
from app.modules.prompts.router import router as prompts_router
from app.modules.settings.router import router as settings_router
from app.modules.audit.router import router as audit_router
from app.modules.alerts.router import router as alerts_router

app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(projects_router)
app.include_router(jobs_router)
app.include_router(delivery_router)
app.include_router(executions_router)
app.include_router(prompts_router)
app.include_router(settings_router)
app.include_router(audit_router)
app.include_router(alerts_router)


# -------------------------------------------------------------------------
# Health Check
# -------------------------------------------------------------------------


@app.get('/', tags=['Health'])
async def health_check() -> dict[str, str]:
    """Endpoint de health check simples da aplicacao."""
    return {
        'status': 'healthy',
        'service': 'AgentVision API',
        'version': '1.0.0',
    }


@app.get('/api/health', tags=['Health'])
async def api_health_check() -> dict:
    """
    Health check abrangente com status de cada componente.

    Retorna status de PostgreSQL, Redis, MinIO e Celery.
    Status geral: healthy (todos OK), degraded (algum falhou),
    unhealthy (componente critico falhou).
    """
    import time

    from app.shared.logging import get_logger as _get_logger

    _health_logger = _get_logger('health_check')
    components: dict[str, dict] = {}

    # --- PostgreSQL ---
    try:
        start = time.monotonic()
        db = SessionLocal()
        try:
            from sqlalchemy import text
            result = db.execute(text('SELECT 1')).scalar()
            latency = round((time.monotonic() - start) * 1000, 1)
            components['postgresql'] = {
                'status': 'healthy',
                'latency_ms': latency,
                'details': f'Query test OK (result={result})',
            }
        finally:
            db.close()
    except Exception as e:
        components['postgresql'] = {
            'status': 'unhealthy',
            'error': str(e)[:200],
        }

    # --- Redis ---
    try:
        start = time.monotonic()
        from app.shared.redis_client import get_redis_client
        redis_client = get_redis_client()
        pong = redis_client.ping()
        info = redis_client.info('memory')
        latency = round((time.monotonic() - start) * 1000, 1)
        components['redis'] = {
            'status': 'healthy' if pong else 'unhealthy',
            'latency_ms': latency,
            'details': {
                'used_memory_human': info.get('used_memory_human', 'N/A'),
                'connected_clients': info.get('connected_clients', 'N/A'),
            },
        }
    except Exception as e:
        components['redis'] = {
            'status': 'unhealthy',
            'error': str(e)[:200],
        }

    # --- MinIO ---
    try:
        start = time.monotonic()
        from app.shared.storage import StorageClient
        storage = StorageClient()
        storage._client.head_bucket(Bucket=storage._bucket)
        latency = round((time.monotonic() - start) * 1000, 1)
        components['minio'] = {
            'status': 'healthy',
            'latency_ms': latency,
            'details': f'Bucket "{storage._bucket}" acessivel',
        }
    except Exception as e:
        components['minio'] = {
            'status': 'degraded',
            'error': str(e)[:200],
        }

    # --- Celery Workers ---
    try:
        start = time.monotonic()
        from app.celery_app import celery_app as _celery
        inspector = _celery.control.inspect(timeout=3.0)
        ping_result = inspector.ping() or {}
        latency = round((time.monotonic() - start) * 1000, 1)
        worker_count = len(ping_result)
        components['celery'] = {
            'status': 'healthy' if worker_count > 0 else 'degraded',
            'latency_ms': latency,
            'details': {
                'workers_online': worker_count,
                'worker_names': list(ping_result.keys()),
            },
        }
    except Exception as e:
        components['celery'] = {
            'status': 'degraded',
            'error': str(e)[:200],
        }

    # --- Status geral ---
    statuses = [c['status'] for c in components.values()]
    if all(s == 'healthy' for s in statuses):
        overall = 'healthy'
    elif any(s == 'unhealthy' for s in statuses):
        overall = 'unhealthy'
    else:
        overall = 'degraded'

    return {
        'status': overall,
        'service': 'AgentVision API',
        'version': '1.0.0',
        'components': components,
    }
