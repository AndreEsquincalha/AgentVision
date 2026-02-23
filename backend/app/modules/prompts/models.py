from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import SoftDeleteModel


class PromptTemplate(SoftDeleteModel):
    """
    Modelo de template de prompt.

    Representa um template reutilizavel de prompt para os agentes de IA.
    Inclui versionamento automatico: a cada atualizacao, o campo version
    e incrementado.
    Herda de SoftDeleteModel (inclui id, created_at, updated_at, deleted_at).
    """

    __tablename__ = 'prompt_templates'

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        default=None,
    )
    category: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
        default=None,
    )
    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
    )
