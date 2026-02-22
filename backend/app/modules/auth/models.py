from sqlalchemy import Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import SoftDeleteModel


class User(SoftDeleteModel):
    """
    Modelo de usuario do sistema.

    Armazena dados de autenticacao e identificacao do usuario.
    Herda de SoftDeleteModel (inclui id, created_at, updated_at, deleted_at).
    """

    __tablename__ = 'users'

    email: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    hashed_password: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )
