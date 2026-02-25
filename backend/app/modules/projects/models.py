from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Float, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.shared.models import SoftDeleteModel

if TYPE_CHECKING:
    from app.modules.jobs.models import Job


class Project(SoftDeleteModel):
    """
    Modelo de projeto do sistema.

    Representa um projeto de automacao com configuracoes de navegacao,
    credenciais de acesso ao site alvo e configuracoes do provedor LLM.
    Herda de SoftDeleteModel (inclui id, created_at, updated_at, deleted_at).
    """

    __tablename__ = 'projects'

    # --- Campos basicos ---
    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )
    base_url: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        default=None,
    )
    encrypted_credentials: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        default=None,
    )

    # --- Configuracoes LLM ---
    llm_provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    llm_model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    encrypted_llm_api_key: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        default=None,
    )
    llm_temperature: Mapped[float] = mapped_column(
        Float,
        nullable=False,
        default=0.7,
    )
    llm_max_tokens: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=4096,
    )
    llm_timeout: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=120,
    )

    # --- Sandbox / Seguranca ---
    allowed_domains: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
    )
    blocked_urls: Mapped[list | None] = mapped_column(
        JSON,
        nullable=True,
        default=None,
    )

    # --- Status ---
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    # --- Relacionamentos ---
    jobs: Mapped[list['Job']] = relationship(
        'Job',
        back_populates='project',
        lazy='selectin',
    )
