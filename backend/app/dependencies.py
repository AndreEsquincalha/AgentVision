from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.modules.auth.models import User
from app.modules.auth.repository import TokenBlacklistRepository, UserRepository
from app.modules.auth.service import AuthService
from app.shared.storage import StorageClient
from app.shared.exceptions import ForbiddenException

# Esquema OAuth2 para extracao do token do header Authorization
oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/api/auth/login')


def get_storage_client() -> StorageClient:
    """Dependency que fornece o cliente de storage (MinIO/S3)."""
    return StorageClient()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Dependency que valida o token JWT e retorna o usuario autenticado.

    Extrai o token Bearer do header Authorization, decodifica e valida o JWT,
    e retorna o modelo User correspondente.

    Args:
        token: Token JWT extraido automaticamente do header Authorization.
        db: Sessao do banco de dados.

    Returns:
        Modelo User do usuario autenticado.

    Raises:
        UnauthorizedException: Se o token for invalido ou o usuario nao existir.
    """
    repository = UserRepository(db)
    token_repository = TokenBlacklistRepository(db)
    service = AuthService(repository, token_repository)
    return service.get_current_user_data(token)


def require_roles(*allowed_roles: str):
    """
    Dependency para exigir roles especificas.
    """

    def _role_dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise ForbiddenException('Permissao insuficiente para esta acao')
        return current_user

    return _role_dependency
