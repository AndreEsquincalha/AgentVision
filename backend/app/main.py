import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.shared.exceptions import (
    BadRequestException,
    ForbiddenException,
    NotFoundException,
    UnauthorizedException,
)

logger = logging.getLogger(__name__)

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

app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(projects_router)
app.include_router(jobs_router)
app.include_router(delivery_router)
app.include_router(executions_router)
app.include_router(prompts_router)
app.include_router(settings_router)


# -------------------------------------------------------------------------
# Health Check
# -------------------------------------------------------------------------


@app.get('/', tags=['Health'])
async def health_check() -> dict[str, str]:
    """Endpoint de health check da aplicacao."""
    return {
        'status': 'healthy',
        'service': 'AgentVision API',
        'version': '1.0.0',
    }


@app.get('/api/health', tags=['Health'])
async def api_health_check() -> dict[str, str]:
    """Endpoint de health check da API."""
    return {
        'status': 'healthy',
        'service': 'AgentVision API',
        'version': '1.0.0',
    }
