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


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Gerencia o ciclo de vida da aplicacao (startup/shutdown)."""
    # Startup: inicializacoes necessarias
    yield
    # Shutdown: limpeza de recursos


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
    allow_methods=['*'],
    allow_headers=['*'],
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

app.include_router(auth_router)


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
