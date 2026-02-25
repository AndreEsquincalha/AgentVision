import uuid

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.shared.models import BaseModel


class TokenUsage(BaseModel):
    """
    Modelo de registro de uso de tokens LLM.

    Armazena o consumo de tokens por execucao, incluindo provider,
    modelo, contagem de tokens de entrada/saida, numero de imagens
    e custo estimado em USD.
    """

    __tablename__ = 'token_usage'

    execution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey('executions.id', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    provider: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )
    model: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
    )
    input_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    output_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    total_tokens: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    image_count: Mapped[int] = mapped_column(
        Integer,
        default=0,
    )
    estimated_cost_usd: Mapped[float] = mapped_column(
        Float,
        default=0.0,
    )
