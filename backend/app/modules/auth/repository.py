import uuid

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.modules.auth.models import TokenBlacklist, User


class UserRepository:
    """
    Repositorio de acesso a dados de usuarios.

    Responsavel por operacoes de leitura e escrita na tabela users.
    Nao contem logica de negocio.
    """

    def __init__(self, db: Session) -> None:
        """Inicializa o repositorio com a sessao do banco."""
        self._db = db

    def get_by_email(self, email: str) -> User | None:
        """
        Busca um usuario pelo email.

        Args:
            email: Email do usuario.

        Returns:
            Usuario encontrado ou None.
        """
        stmt = select(User).where(
            User.email == email,
            User.deleted_at.is_(None),
        )
        return self._db.execute(stmt).scalar_one_or_none()

    def get_by_id(self, user_id: uuid.UUID) -> User | None:
        """
        Busca um usuario pelo ID.

        Args:
            user_id: ID (UUID) do usuario.

        Returns:
            Usuario encontrado ou None.
        """
        stmt = select(User).where(
            User.id == user_id,
            User.deleted_at.is_(None),
        )
        return self._db.execute(stmt).scalar_one_or_none()

    def create(self, user_data: dict) -> User:
        """
        Cria um novo usuario no banco de dados.

        Args:
            user_data: Dicionario com os dados do usuario
                       (email, hashed_password, name, is_active).

        Returns:
            Usuario criado.
        """
        user = User(**user_data)
        self._db.add(user)
        self._db.commit()
        self._db.refresh(user)
        return user


class TokenBlacklistRepository:
    """
    Repositorio de tokens revogados.
    """

    def __init__(self, db: Session) -> None:
        """Inicializa o repositorio com a sessao do banco."""
        self._db = db

    def add(self, jti: str, expires_at: datetime) -> TokenBlacklist:
        """
        Adiciona um token revogado.
        """
        token = TokenBlacklist(jti=jti, expires_at=expires_at)
        self._db.add(token)
        self._db.commit()
        self._db.refresh(token)
        return token

    def is_blacklisted(self, jti: str) -> bool:
        """
        Verifica se um token esta na blacklist.
        """
        stmt = select(TokenBlacklist).where(TokenBlacklist.jti == jti)
        return self._db.execute(stmt).scalar_one_or_none() is not None

    def cleanup_expired(self, now: datetime) -> int:
        """
        Remove tokens expirados da blacklist.
        """
        stmt = delete(TokenBlacklist).where(TokenBlacklist.expires_at < now)
        result = self._db.execute(stmt)
        self._db.commit()
        return int(result.rowcount or 0)
