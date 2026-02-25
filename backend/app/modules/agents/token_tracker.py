import logging
import uuid

from app.database import SessionLocal

logger = logging.getLogger(__name__)


class TokenTracker:
    """
    Registra uso de tokens em cada chamada LLM.

    Grava na tabela token_usage e calcula custo estimado
    com base nos precos publicos de cada provider.
    """

    # Custos por milhao de tokens (USD) — precos aproximados
    COST_PER_MILLION: dict[str, dict[str, float]] = {
        'anthropic': {'input': 3.0, 'output': 15.0},   # Claude Sonnet
        'openai': {'input': 2.5, 'output': 10.0},      # GPT-4o
        'google': {'input': 0.10, 'output': 0.40},     # Gemini Flash
        'ollama': {'input': 0.0, 'output': 0.0},       # Local — sem custo
    }

    @staticmethod
    def calculate_cost(
        provider: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        """
        Calcula custo estimado em USD.

        Args:
            provider: Nome do provider (anthropic, openai, google, ollama).
            input_tokens: Tokens de entrada consumidos.
            output_tokens: Tokens de saida consumidos.

        Returns:
            Custo estimado em USD.
        """
        costs = TokenTracker.COST_PER_MILLION.get(
            provider.lower(),
            {'input': 0.0, 'output': 0.0},
        )
        input_cost = (input_tokens / 1_000_000) * costs['input']
        output_cost = (output_tokens / 1_000_000) * costs['output']
        return round(input_cost + output_cost, 6)

    @staticmethod
    def record_usage(
        execution_id: str,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        image_count: int = 0,
    ) -> None:
        """
        Grava registro de uso de tokens no banco de dados.

        Cria sua propria sessao DB porque pode ser chamado de dentro
        de uma Celery task (fora do contexto FastAPI).

        Args:
            execution_id: ID da execucao (UUID como string).
            provider: Nome do provider LLM.
            model: Nome do modelo utilizado.
            input_tokens: Tokens de entrada consumidos.
            output_tokens: Tokens de saida consumidos.
            image_count: Numero de imagens analisadas.
        """
        # Importa aqui para evitar circular
        from app.modules.agents.token_usage_model import TokenUsage

        total_tokens = input_tokens + output_tokens
        estimated_cost = TokenTracker.calculate_cost(
            provider, input_tokens, output_tokens,
        )

        db = SessionLocal()
        try:
            usage = TokenUsage(
                execution_id=uuid.UUID(execution_id),
                provider=provider.lower(),
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=total_tokens,
                image_count=image_count,
                estimated_cost_usd=estimated_cost,
            )
            db.add(usage)
            db.commit()

            logger.info(
                'TokenTracker: registrado uso — exec=%s, provider=%s, '
                'model=%s, in=%d, out=%d, total=%d, custo=$%.6f',
                execution_id,
                provider,
                model,
                input_tokens,
                output_tokens,
                total_tokens,
                estimated_cost,
            )
        except Exception as e:
            db.rollback()
            logger.error(
                'TokenTracker: erro ao registrar uso de tokens — %s', str(e),
            )
        finally:
            db.close()

    @staticmethod
    def get_usage_for_period(
        date_from: 'datetime | None' = None,
        date_to: 'datetime | None' = None,
        provider: str | None = None,
    ) -> list[dict]:
        """
        Consulta registros de uso de tokens por periodo e provider.

        Args:
            date_from: Inicio do periodo (inclusive).
            date_to: Fim do periodo (inclusive).
            provider: Filtro por provider (opcional).

        Returns:
            Lista de dicionarios com dados de uso.
        """
        from datetime import datetime

        from sqlalchemy import func, select

        from app.modules.agents.token_usage_model import TokenUsage

        db = SessionLocal()
        try:
            stmt = select(
                TokenUsage.provider,
                func.sum(TokenUsage.input_tokens).label('total_input'),
                func.sum(TokenUsage.output_tokens).label('total_output'),
                func.sum(TokenUsage.total_tokens).label('total_tokens'),
                func.sum(TokenUsage.image_count).label('total_images'),
                func.sum(TokenUsage.estimated_cost_usd).label('total_cost'),
                func.count(TokenUsage.id).label('call_count'),
            ).group_by(TokenUsage.provider)

            if date_from is not None:
                stmt = stmt.where(TokenUsage.created_at >= date_from)
            if date_to is not None:
                stmt = stmt.where(TokenUsage.created_at <= date_to)
            if provider is not None:
                stmt = stmt.where(TokenUsage.provider == provider.lower())

            results = db.execute(stmt).all()

            return [
                {
                    'provider': row.provider,
                    'total_input_tokens': row.total_input or 0,
                    'total_output_tokens': row.total_output or 0,
                    'total_tokens': row.total_tokens or 0,
                    'total_images': row.total_images or 0,
                    'estimated_cost_usd': round(float(row.total_cost or 0), 6),
                    'call_count': row.call_count or 0,
                }
                for row in results
            ]
        except Exception as e:
            logger.error(
                'TokenTracker: erro ao consultar uso — %s', str(e),
            )
            return []
        finally:
            db.close()

    @staticmethod
    def get_total_tokens_for_period(
        date_from: 'datetime | None' = None,
        date_to: 'datetime | None' = None,
    ) -> int:
        """
        Retorna o total de tokens consumidos em um periodo.

        Args:
            date_from: Inicio do periodo (inclusive).
            date_to: Fim do periodo (inclusive).

        Returns:
            Total de tokens no periodo.
        """
        from sqlalchemy import func, select

        from app.modules.agents.token_usage_model import TokenUsage

        db = SessionLocal()
        try:
            stmt = select(
                func.coalesce(func.sum(TokenUsage.total_tokens), 0),
            )

            if date_from is not None:
                stmt = stmt.where(TokenUsage.created_at >= date_from)
            if date_to is not None:
                stmt = stmt.where(TokenUsage.created_at <= date_to)

            result: int = db.execute(stmt).scalar_one()
            return result
        except Exception as e:
            logger.error(
                'TokenTracker: erro ao consultar total de tokens — %s', str(e),
            )
            return 0
        finally:
            db.close()
