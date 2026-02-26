from datetime import datetime
from enum import Enum

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column
from app.shared.models import BaseModel, SoftDeleteModel


class UserRole(str, Enum):
    """Roles basicos do sistema."""

    admin = 'admin'
    operator = 'operator'
    viewer = 'viewer'


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
    role: Mapped[str] = mapped_column(
        String(20),
        default=UserRole.admin.value,
        nullable=False,
    )


class TokenBlacklist(BaseModel):
    """
    Tokens JWT revogados (logout).

    Armazena o JTI do token e a data de expiracao para cleanup.
    """

    __tablename__ = 'token_blacklist'

    jti: Mapped[str] = mapped_column(
        String(64),
        unique=True,
        nullable=False,
        index=True,
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        index=True,
    )
