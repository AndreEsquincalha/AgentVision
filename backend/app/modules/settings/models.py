from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import BaseModel


class Setting(BaseModel):
    """
    Modelo de configuracao do sistema.

    Armazena pares chave-valor criptografados, organizados por categoria.
    Usado para configuracoes sensiveis como SMTP, chaves de API, etc.
    Herda de BaseModel (inclui id, created_at, updated_at).
    NAO possui soft delete — configuracoes sao excluidas permanentemente.
    """

    __tablename__ = 'settings'

    key: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        unique=True,
        index=True,
    )
    encrypted_value: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    category: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        index=True,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        default=None,
    )
