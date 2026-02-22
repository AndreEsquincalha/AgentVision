from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.auth.repository import UserRepository
from app.modules.auth.schemas import (
    LoginRequest,
    RefreshRequest,
    TokenResponse,
    UserResponse,
)
from app.modules.auth.service import AuthService

router = APIRouter(
    prefix='/api/auth',
    tags=['Auth'],
)


def get_user_repository(db: Session = Depends(get_db)) -> UserRepository:
    """Dependency que fornece o repositorio de usuarios."""
    return UserRepository(db)


def get_auth_service(
    repository: UserRepository = Depends(get_user_repository),
) -> AuthService:
    """Dependency que fornece o servico de autenticacao."""
    return AuthService(repository)


@router.post('/login', response_model=TokenResponse)
def login(
    data: LoginRequest,
    service: AuthService = Depends(get_auth_service),
) -> TokenResponse:
    """
    Autentica o usuario com email e senha.

    Retorna access_token e refresh_token em caso de sucesso.
    """
    return service.authenticate(data.email, data.password)


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


@router.get('/me', response_model=UserResponse)
def get_me(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    """
    Retorna os dados do usuario autenticado.

    Requer um access token valido no header Authorization.
    """
    return UserResponse.model_validate(current_user)
