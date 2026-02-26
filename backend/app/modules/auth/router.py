from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user, oauth2_scheme, require_roles
from app.modules.auth.models import User
from app.modules.auth.repository import TokenBlacklistRepository, UserRepository
from app.modules.auth.schemas import (
    LoginRequest,
    LogoutRequest,
    RefreshRequest,
    TokenResponse,
    UnlockAccountRequest,
    UserResponse,
)
from app.modules.auth.service import AuthService
from app.modules.audit.repository import AuditLogRepository
from app.modules.audit.service import AuditLogService
from app.shared.redis_client import get_redis_client

router = APIRouter(
    prefix='/api/auth',
    tags=['Auth'],
)

# Limites de seguranca
_LOGIN_LIMIT_IP = 5
_LOGIN_LIMIT_EMAIL = 10
_LOGIN_WINDOW_SECONDS = 60
_LOCKOUT_THRESHOLD = 5
_LOCKOUT_SECONDS = 15 * 60


def _get_client_ip(request: Request) -> str:
    """Obtencao de IP do cliente com suporte a proxy."""
    forwarded = request.headers.get('x-forwarded-for')
    if forwarded:
        return forwarded.split(',')[0].strip()
    if request.client:
        return request.client.host
    return 'unknown'


def _increment_with_ttl(key: str, ttl: int) -> tuple[int, int]:
    """Incrementa contador com TTL e retorna (count, retry_after)."""
    redis_client = get_redis_client()
    count = int(redis_client.incr(key))
    if count == 1:
        redis_client.expire(key, ttl)
    retry_after = int(redis_client.ttl(key))
    redis_client.close()
    return count, max(retry_after, 0)


def _is_locked(email: str) -> int:
    """Retorna segundos restantes de lockout (0 se nao bloqueado)."""
    redis_client = get_redis_client()
    ttl = redis_client.ttl(f'login_lockout:{email}')
    redis_client.close()
    return int(ttl or 0)


def _register_failed_login(email: str) -> int:
    """Incrementa tentativas falhadas e retorna tentativas atuais."""
    redis_client = get_redis_client()
    key = f'login_attempts:{email}'
    attempts = int(redis_client.incr(key))
    if attempts == 1:
        redis_client.expire(key, _LOCKOUT_SECONDS)
    if attempts >= _LOCKOUT_THRESHOLD:
        redis_client.setex(f'login_lockout:{email}', _LOCKOUT_SECONDS, '1')
        redis_client.delete(key)
    redis_client.close()
    return attempts


def _reset_login_attempts(email: str) -> None:
    """Limpa contador e lockout de login."""
    redis_client = get_redis_client()
    redis_client.delete(f'login_attempts:{email}')
    redis_client.delete(f'login_lockout:{email}')
    redis_client.close()


def _safe_audit(audit_service: AuditLogService, **kwargs) -> None:
    """Registra auditoria sem quebrar o fluxo."""
    try:
        audit_service.create_log(**kwargs)
    except Exception:
        pass


def get_user_repository(db: Session = Depends(get_db)) -> UserRepository:
    """Dependency que fornece o repositorio de usuarios."""
    return UserRepository(db)


def get_auth_service(
    db: Session = Depends(get_db),
) -> AuthService:
    """Dependency que fornece o servico de autenticacao."""
    repository = UserRepository(db)
    token_repository = TokenBlacklistRepository(db)
    return AuthService(repository, token_repository)


def get_audit_service(db: Session = Depends(get_db)) -> AuditLogService:
    """Dependency que fornece o servico de auditoria."""
    return AuditLogService(AuditLogRepository(db))


@router.post('/login', response_model=TokenResponse)
def login(
    data: LoginRequest,
    request: Request,
    service: AuthService = Depends(get_auth_service),
    repository: UserRepository = Depends(get_user_repository),
    audit_service: AuditLogService = Depends(get_audit_service),
) -> TokenResponse:
    """
    Autentica o usuario com email e senha.

    Retorna access_token e refresh_token em caso de sucesso.
    """
    email = data.email
    ip = _get_client_ip(request)

    # Rate limit por IP
    ip_key = f'login_rate:ip:{ip}'
    ip_count, ip_retry = _increment_with_ttl(ip_key, _LOGIN_WINDOW_SECONDS)
    if ip_count > _LOGIN_LIMIT_IP:
        _safe_audit(
            audit_service,
            action='login_rate_limited',
            resource_type='auth',
            resource_id=None,
            user_id=None,
            ip_address=ip,
            details={'scope': 'ip', 'email': email},
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail='Muitas tentativas. Tente novamente mais tarde.',
            headers={'Retry-After': str(ip_retry)},
        )

    # Rate limit por email
    email_key = f'login_rate:email:{email}'
    email_count, email_retry = _increment_with_ttl(email_key, _LOGIN_WINDOW_SECONDS)
    if email_count > _LOGIN_LIMIT_EMAIL:
        _safe_audit(
            audit_service,
            action='login_rate_limited',
            resource_type='auth',
            resource_id=None,
            user_id=None,
            ip_address=ip,
            details={'scope': 'email', 'email': email},
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail='Muitas tentativas. Tente novamente mais tarde.',
            headers={'Retry-After': str(email_retry)},
        )

    # Lockout por tentativas falhadas
    lockout_ttl = _is_locked(email)
    if lockout_ttl > 0:
        _safe_audit(
            audit_service,
            action='login_blocked',
            resource_type='auth',
            resource_id=None,
            user_id=None,
            ip_address=ip,
            details={'email': email, 'reason': 'lockout'},
        )
        raise HTTPException(
            status_code=423,
            detail='Conta bloqueada temporariamente. Tente novamente em alguns minutos.',
            headers={'Retry-After': str(lockout_ttl)},
        )

    try:
        token_response = service.authenticate(email, data.password)
        _reset_login_attempts(email)
        user = repository.get_by_email(email)
        _safe_audit(
            audit_service,
            action='login',
            resource_type='auth',
            resource_id=str(user.id) if user else None,
            user_id=user.id if user else None,
            ip_address=ip,
            details=None,
        )
        return token_response
    except Exception:
        attempts = _register_failed_login(email)
        if attempts >= _LOCKOUT_THRESHOLD:
            _safe_audit(
                audit_service,
                action='login_blocked',
                resource_type='auth',
                resource_id=None,
                user_id=None,
                ip_address=ip,
                details={'email': email, 'reason': 'lockout_threshold'},
            )
            raise HTTPException(
                status_code=423,
                detail='Conta bloqueada por excesso de tentativas.',
                headers={'Retry-After': str(_LOCKOUT_SECONDS)},
            )
        _safe_audit(
            audit_service,
            action='login_failed',
            resource_type='auth',
            resource_id=None,
            user_id=None,
            ip_address=ip,
            details={'email': email},
        )
        raise


@router.post('/refresh', response_model=TokenResponse)
def refresh_token(
    data: RefreshRequest,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """
    Renova os tokens usando um refresh token valido.

    Retorna novos access_token e refresh_token.
    """
    return service.refresh_token(data.refresh_token)


@router.post('/logout')
def logout(
    request: Request,
    data: LogoutRequest | None = None,
    current_user: User = Depends(get_current_user),
    service: AuthService = Depends(get_auth_service),
    audit_service: AuditLogService = Depends(get_audit_service),
    token: str = Depends(oauth2_scheme),
) -> dict:
    """
    Realiza logout seguro com blacklist do token.
    """
    ip = _get_client_ip(request)
    # O token do access esta no header Authorization
    if token:
        service.blacklist_token(token)
    if data and data.refresh_token:
        try:
            service.blacklist_token(data.refresh_token)
        except Exception:
            pass

    _safe_audit(
        audit_service,
        action='logout',
        resource_type='auth',
        resource_id=str(current_user.id),
        user_id=current_user.id,
        ip_address=ip,
        details=None,
    )
    return {'success': True, 'message': 'Logout realizado com sucesso'}


@router.get('/me', response_model=UserResponse)
def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """
    Retorna os dados do usuario autenticado.

    Requer um access token valido no header Authorization.
    """
    return UserResponse.model_validate(current_user)


@router.post('/unlock', response_model=dict)
def unlock_account(
    data: UnlockAccountRequest,
    current_user: User = Depends(require_roles('admin')),
    audit_service: AuditLogService = Depends(get_audit_service),
) -> dict:
    """
    Desbloqueia uma conta manualmente (admin).
    """
    _reset_login_attempts(data.email)
    _safe_audit(
        audit_service,
        action='unlock_account',
        resource_type='auth',
        resource_id=None,
        user_id=current_user.id,
        ip_address=None,
        details={'email': data.email},
    )
    return {'success': True, 'message': 'Conta desbloqueada'}
