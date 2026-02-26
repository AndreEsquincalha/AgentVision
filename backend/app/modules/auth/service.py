import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
from jose import JWTError, jwt

from app.config import settings
from app.modules.auth.models import User
from app.modules.auth.repository import TokenBlacklistRepository, UserRepository
from app.modules.auth.schemas import TokenResponse
from app.shared.exceptions import UnauthorizedException


def hash_password(password: str) -> str:
    """
    Gera o hash bcrypt de uma senha.

    Args:
        password: Senha em texto puro.

    Returns:
        Hash bcrypt da senha.
    """
    return bcrypt.hashpw(
        password.encode('utf-8'), bcrypt.gensalt()
    ).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verifica se uma senha em texto puro corresponde ao hash.

    Args:
        plain_password: Senha em texto puro.
        hashed_password: Hash bcrypt armazenado.

    Returns:
        True se a senha corresponde ao hash.
    """
    return bcrypt.checkpw(
        plain_password.encode('utf-8'),
        hashed_password.encode('utf-8'),
    )


def create_access_token(subject: str) -> str:
    """
    Cria um JWT access token.

    Args:
        subject: Identificador do usuario (UUID como string).

    Returns:
        Token JWT assinado.
    """
    now = datetime.now(UTC)
    expire = now + timedelta(
        minutes=settings.jwt_access_token_expire_minutes
    )
    to_encode = {
        'sub': subject,
        'exp': expire,
        'iat': now,
        'jti': str(uuid.uuid4()),
        'type': 'access',
    }
    encoded_jwt: str = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return encoded_jwt


def create_refresh_token(subject: str) -> str:
    """
    Cria um JWT refresh token.

    Args:
        subject: Identificador do usuario (UUID como string).

    Returns:
        Token JWT assinado.
    """
    now = datetime.now(UTC)
    expire = now + timedelta(
        days=settings.jwt_refresh_token_expire_days
    )
    to_encode = {
        'sub': subject,
        'exp': expire,
        'iat': now,
        'jti': str(uuid.uuid4()),
        'type': 'refresh',
    }
    encoded_jwt: str = jwt.encode(
        to_encode,
        settings.jwt_secret_key,
        algorithm=settings.jwt_algorithm,
    )
    return encoded_jwt


def decode_token(token: str) -> dict:
    """
    Decodifica e valida um token JWT.

    Args:
        token: Token JWT a ser decodificado.

    Returns:
        Payload do token decodificado.

    Raises:
        UnauthorizedException: Se o token for invalido ou expirado.
    """
    try:
        payload: dict = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return payload
    except JWTError:
        raise UnauthorizedException('Token invalido ou expirado')


class AuthService:
    """
    Servico de autenticacao.

    Contem a logica de negocio para login, refresh de tokens
    e obtencao de dados do usuario autenticado.
    """

    def __init__(
        self,
        repository: UserRepository,
        token_repository: TokenBlacklistRepository | None = None,
    ) -> None:
        """Inicializa o servico com os repositorios necessarios."""
        self._repository = repository
        self._token_repository = token_repository

    def authenticate(self, email: str, password: str) -> TokenResponse:
        """
        Autentica um usuario com email e senha.

        Args:
            email: Email do usuario.
            password: Senha em texto puro.

        Returns:
            TokenResponse com access_token e refresh_token.

        Raises:
            UnauthorizedException: Se as credenciais forem invalidas.
        """
        user = self._repository.get_by_email(email)

        if not user:
            raise UnauthorizedException('Credenciais invalidas')

        if not verify_password(password, user.hashed_password):
            raise UnauthorizedException('Credenciais invalidas')

        if not user.is_active:
            raise UnauthorizedException('Usuario desativado')

        access_token = create_access_token(str(user.id))
        refresh_token = create_refresh_token(str(user.id))

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
        )

    def refresh_token(self, refresh_token_str: str) -> TokenResponse:
        """
        Renova os tokens usando um refresh token valido.

        Args:
            refresh_token_str: Refresh token JWT.

        Returns:
            TokenResponse com novos access_token e refresh_token.

        Raises:
            UnauthorizedException: Se o refresh token for invalido.
        """
        payload = decode_token(refresh_token_str)

        # Verifica se e um refresh token
        token_type = payload.get('type')
        if token_type != 'refresh':
            raise UnauthorizedException('Token invalido: tipo incorreto')

        jti = payload.get('jti')
        if jti and self._token_repository:
            if self._token_repository.is_blacklisted(jti):
                raise UnauthorizedException('Token revogado')

        subject = payload.get('sub')
        if not subject:
            raise UnauthorizedException('Token invalido: subject ausente')

        # Verifica se o usuario ainda existe e esta ativo
        user = self._repository.get_by_id(uuid.UUID(subject))
        if not user:
            raise UnauthorizedException('Usuario nao encontrado')

        if not user.is_active:
            raise UnauthorizedException('Usuario desativado')

        # Gera novos tokens
        new_access_token = create_access_token(str(user.id))
        new_refresh_token = create_refresh_token(str(user.id))

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
        )

    def get_current_user_data(self, token: str) -> User:
        """
        Obtem o usuario a partir de um access token.

        Args:
            token: Access token JWT.

        Returns:
            Modelo User do usuario autenticado.

        Raises:
            UnauthorizedException: Se o token for invalido ou o usuario nao existir.
        """
        payload = decode_token(token)

        # Verifica se e um access token
        token_type = payload.get('type')
        if token_type != 'access':
            raise UnauthorizedException('Token invalido: tipo incorreto')

        jti = payload.get('jti')
        if jti and self._token_repository:
            if self._token_repository.is_blacklisted(jti):
                raise UnauthorizedException('Token revogado')

        subject = payload.get('sub')
        if not subject:
            raise UnauthorizedException('Token invalido: subject ausente')

        user = self._repository.get_by_id(uuid.UUID(subject))
        if not user:
            raise UnauthorizedException('Usuario nao encontrado')

        if not user.is_active:
            raise UnauthorizedException('Usuario desativado')

        return user

    def blacklist_token(self, token: str) -> None:
        """
        Adiciona um token JWT na blacklist.
        """
        if not self._token_repository:
            raise UnauthorizedException('Repositorio de tokens nao configurado')

        payload = decode_token(token)
        jti = payload.get('jti')
        exp = payload.get('exp')
        if not jti or not exp:
            raise UnauthorizedException('Token invalido para blacklist')

        expires_at = datetime.fromtimestamp(exp, tz=UTC)
        if not self._token_repository.is_blacklisted(jti):
            self._token_repository.add(jti, expires_at)
