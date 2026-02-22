import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.auth.models import User


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
