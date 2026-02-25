import hashlib
import json
import logging
from datetime import datetime, timezone

from app.modules.agents.llm_provider import AnalysisResult, get_llm_provider

logger = logging.getLogger(__name__)

# Prompt compacto (~200 tokens) que instrui o LLM a retornar analise estruturada.
# Reduzido de ~500 tokens para economizar consumo sem perder instrucoes essenciais.
_SYSTEM_PROMPT_TEMPLATE = '''Analise as {num_screenshots} screenshots de paginas web.

Contexto:
{context}

Instrucoes:
{user_prompt}

Responda em DUAS partes:

1. ANALISE: Descricao do conteudo visual, informacoes encontradas, observacoes e status.

2. DADOS JSON:
```json
{{
    "title": "Titulo principal",
    "summary": "Resumo conciso",
    "extracted_fields": {{}},
    "insights": [],
    "status": "success|partial|error",
    "confidence": 0.0
}}
```'''

# TTL do cache em segundos (1 hora)
_CACHE_TTL_SECONDS: int = 3600


class VisionAnalyzer:
    """
    Analisador visual que utiliza provedores LLM para extrair informacoes de screenshots.

    Recebe screenshots em bytes e um prompt de analise, constroi um prompt contextual
    abrangente e envia para o provedor LLM configurado para obter analise textual
    e dados estruturados (JSON).

    Funcionalidades adicionais:
    - Cache Redis para evitar re-analise de screenshots identicos (9.2.5)
    - Validacao de tokens estimados antes de enviar ao LLM (9.2.4)
    - Otimizacao de imagens por provider (9.2.2)
    - Registro de uso de tokens no banco (9.3.2)
    - Controle de budget diario/mensal (9.3.4)
    """

    def __init__(
        self,
        provider_name: str,
        api_key: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: int = 120,
    ) -> None:
        """
        Inicializa o VisionAnalyzer com configuracoes do provedor LLM.

        Args:
            provider_name: Nome do provedor LLM ('anthropic', 'openai', 'google', 'ollama').
            api_key: Chave de API do provedor (para Ollama, pode ser a URL base).
            model: Nome do modelo a ser utilizado.
            temperature: Temperatura para geracao (0.0 a 2.0).
            max_tokens: Numero maximo de tokens na resposta.
            timeout: Timeout em segundos para chamadas a API.
        """
        self._provider_name = provider_name
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout = timeout

        logger.info(
            'Inicializando VisionAnalyzer com provedor %s (modelo: %s)',
            provider_name,
            model,
        )

        # Cria o provedor LLM via factory
        self._provider = get_llm_provider(
            provider_name=provider_name,
            api_key=api_key,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            timeout=timeout,
        )

    @classmethod
    def from_llm_config(cls, llm_config: dict) -> 'VisionAnalyzer':
        """
        Cria uma instancia do VisionAnalyzer a partir de um dicionario de configuracao LLM.

        Metodo de conveniencia que aceita o mesmo formato retornado por
        ProjectService.get_llm_config().

        Args:
            llm_config: Dicionario com configuracoes do LLM contendo as chaves:
                        provider, api_key, model, temperature, max_tokens, timeout.

        Returns:
            Instancia configurada do VisionAnalyzer.
        """
        return cls(
            provider_name=llm_config['provider'],
            api_key=llm_config.get('api_key', ''),
            model=llm_config['model'],
            temperature=llm_config.get('temperature', 0.7),
            max_tokens=llm_config.get('max_tokens', 4096),
            timeout=llm_config.get('timeout', 120),
        )

    def analyze(
        self,
        screenshots: list[bytes],
        prompt: str,
        metadata: dict | None = None,
    ) -> AnalysisResult:
        """
        Analisa screenshots utilizando o provedor LLM configurado.

        Fluxo completo:
        1. Verifica cache Redis para analises identicas
        2. Verifica budget de tokens (diario/mensal)
        3. Otimiza imagens para o provider
        4. Estima tokens e valida contra limite de contexto
        5. Envia para o LLM
        6. Registra uso de tokens no banco
        7. Salva resultado no cache

        Args:
            screenshots: Lista de screenshots em bytes (PNG/JPEG).
            prompt: Prompt de analise do usuario/job.
            metadata: Metadados opcionais para enriquecer o contexto da analise
                      (ex: project_name, job_name, base_url, execution_id).

        Returns:
            AnalysisResult contendo texto da analise, dados extraidos (JSON) e tokens usados.
        """
        if not screenshots:
            logger.warning('VisionAnalyzer: nenhum screenshot fornecido para analise')
            return AnalysisResult(
                text='Nenhum screenshot fornecido para analise.',
                extracted_data=None,
                tokens_used=0,
            )

        logger.info(
            'VisionAnalyzer: iniciando analise de %d screenshot(s) com %s (%s)',
            len(screenshots),
            self._provider_name,
            self._model,
        )

        try:
            # Constroi o prompt completo com contexto e instrucoes
            full_prompt = self._build_prompt(
                user_prompt=prompt,
                num_screenshots=len(screenshots),
                metadata=metadata,
            )

            # ---------------------------------------------------------------
            # 1. Verificar cache Redis
            # ---------------------------------------------------------------
            cache_key = self._compute_cache_key(screenshots, full_prompt)
            cached_result = self._get_cached_result(cache_key)
            if cached_result is not None:
                return cached_result

            # ---------------------------------------------------------------
            # 2. Verificar budget de tokens
            # ---------------------------------------------------------------
            self._check_token_budget()

            # ---------------------------------------------------------------
            # 3. Otimizar imagens para o provider
            # ---------------------------------------------------------------
            optimized_screenshots = self._optimize_images(screenshots)

            # ---------------------------------------------------------------
            # 4. Estimar tokens e validar contra limite de contexto
            # ---------------------------------------------------------------
            estimation = self._provider.estimate_tokens(
                full_prompt, optimized_screenshots,
            )
            context_limit = estimation['context_limit']
            estimated_total = estimation['total']

            if estimated_total > context_limit * 0.9:
                logger.warning(
                    'VisionAnalyzer: estimativa de tokens (%d) proxima do '
                    'limite (%d). Reduzindo screenshots.',
                    estimated_total, context_limit,
                )
                # Estrategia: reduzir para 1 screenshot se estimativa excede 90%
                optimized_screenshots = optimized_screenshots[:1]
                estimation = self._provider.estimate_tokens(
                    full_prompt, optimized_screenshots,
                )

            logger.info(
                'VisionAnalyzer: estimativa de tokens — text=%d, image=%d, '
                'total=%d, limite=%d',
                estimation['text_tokens'],
                estimation['image_tokens'],
                estimation['total'],
                estimation['context_limit'],
            )

            # ---------------------------------------------------------------
            # 5. Envia para o provedor LLM
            # ---------------------------------------------------------------
            if len(optimized_screenshots) == 1:
                result = self._provider.analyze_image(
                    image_data=optimized_screenshots[0],
                    prompt=full_prompt,
                )
            else:
                result = self._provider.analyze_images(
                    images=optimized_screenshots,
                    prompt=full_prompt,
                )

            logger.info(
                'VisionAnalyzer: analise concluida. Tokens usados: %d '
                '(in=%d, out=%d), Dados extraidos: %s',
                result.tokens_used,
                result.input_tokens,
                result.output_tokens,
                'sim' if result.extracted_data else 'nao',
            )

            # ---------------------------------------------------------------
            # 6. Registrar uso de tokens no banco
            # ---------------------------------------------------------------
            execution_id = (metadata or {}).get('execution_id')
            if execution_id and result.tokens_used > 0:
                self._record_token_usage(
                    execution_id=execution_id,
                    result=result,
                    image_count=len(optimized_screenshots),
                )

            # ---------------------------------------------------------------
            # 7. Salvar resultado no cache Redis
            # ---------------------------------------------------------------
            self._set_cached_result(cache_key, result)

            return result

        except Exception as e:
            error_msg = f'Erro na analise visual com {self._provider_name}: {str(e)}'
            logger.error('VisionAnalyzer: %s', error_msg)
            return AnalysisResult(
                text=error_msg,
                extracted_data=None,
                tokens_used=0,
            )

    # ------------------------------------------------------------------
    # Prompt builder
    # ------------------------------------------------------------------

    def _build_prompt(
        self,
        user_prompt: str,
        num_screenshots: int,
        metadata: dict | None = None,
    ) -> str:
        """
        Constroi o prompt completo para envio ao LLM.

        Combina o template de sistema com o prompt do usuario, metadados de contexto
        e instrucoes para saida estruturada.

        Args:
            user_prompt: Prompt de analise do usuario/job.
            num_screenshots: Numero de screenshots sendo analisados.
            metadata: Metadados opcionais para contexto.

        Returns:
            Prompt completo formatado.
        """
        # Monta a secao de contexto com metadados
        context_parts: list[str] = []

        if metadata:
            if metadata.get('project_name'):
                context_parts.append(f'Projeto: {metadata["project_name"]}')
            if metadata.get('job_name'):
                context_parts.append(f'Job: {metadata["job_name"]}')
            if metadata.get('base_url'):
                context_parts.append(f'URL base: {metadata["base_url"]}')
            if metadata.get('execution_id'):
                context_parts.append(f'ID da execucao: {metadata["execution_id"]}')

        context_parts.append(f'Screenshots analisados: {num_screenshots}')
        context_parts.append(
            f'Data/hora da analise: {datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")}'
        )

        context = '\n'.join(f'- {part}' for part in context_parts)

        # Formata o prompt completo usando o template compacto
        full_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
            context=context,
            user_prompt=user_prompt,
            num_screenshots=num_screenshots,
        )

        return full_prompt

    # ------------------------------------------------------------------
    # Cache Redis (9.2.5)
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_cache_key(screenshots: list[bytes], prompt: str) -> str:
        """
        Calcula chave de cache baseada no hash dos screenshots + prompt.

        Args:
            screenshots: Lista de imagens em bytes.
            prompt: Texto completo do prompt.

        Returns:
            Chave de cache no formato 'vision_cache:{sha256}'.
        """
        hasher = hashlib.sha256()
        hasher.update(prompt.encode('utf-8'))
        for img in screenshots:
            hasher.update(hashlib.sha256(img).digest())
        return f'vision_cache:{hasher.hexdigest()}'

    @staticmethod
    def _get_cached_result(cache_key: str) -> AnalysisResult | None:
        """
        Busca resultado no cache Redis.

        Args:
            cache_key: Chave de cache.

        Returns:
            AnalysisResult se encontrado no cache, None caso contrario.
        """
        try:
            from redis import Redis

            from app.config import settings

            redis_client = Redis.from_url(
                settings.redis_url, decode_responses=True,
            )
            cached = redis_client.get(cache_key)
            if cached:
                data = json.loads(cached)
                logger.info(
                    'VisionAnalyzer: cache hit — tokens economizados',
                )
                return AnalysisResult(
                    text=data.get('text', ''),
                    extracted_data=data.get('extracted_data'),
                    tokens_used=0,
                    input_tokens=0,
                    output_tokens=0,
                )
        except Exception as e:
            # Cache miss ou erro de conexao nao e fatal
            logger.debug('VisionAnalyzer: cache miss ou erro — %s', str(e))
        return None

    @staticmethod
    def _set_cached_result(cache_key: str, result: AnalysisResult) -> None:
        """
        Salva resultado no cache Redis com TTL de 1 hora.

        Args:
            cache_key: Chave de cache.
            result: Resultado da analise para cachear.
        """
        try:
            from redis import Redis

            from app.config import settings

            redis_client = Redis.from_url(
                settings.redis_url, decode_responses=True,
            )
            cache_data = json.dumps({
                'text': result.text,
                'extracted_data': result.extracted_data,
            })
            redis_client.setex(cache_key, _CACHE_TTL_SECONDS, cache_data)
            logger.debug('VisionAnalyzer: resultado salvo no cache')
        except Exception as e:
            # Falha no cache nao e erro fatal
            logger.debug('VisionAnalyzer: erro ao salvar no cache — %s', str(e))

    # ------------------------------------------------------------------
    # Image optimization (9.2.2)
    # ------------------------------------------------------------------

    def _optimize_images(self, screenshots: list[bytes]) -> list[bytes]:
        """
        Otimiza screenshots para o provider LLM configurado.

        Args:
            screenshots: Lista de imagens em bytes originais.

        Returns:
            Lista de imagens otimizadas.
        """
        try:
            from app.modules.agents.image_optimizer import ImageOptimizer

            optimized, stats = ImageOptimizer.optimize_batch(
                screenshots, self._provider_name,
            )
            if stats['savings_percent'] > 0:
                logger.info(
                    'VisionAnalyzer: imagens otimizadas — economia de %.1f%%',
                    stats['savings_percent'],
                )
            return optimized
        except Exception as e:
            logger.warning(
                'VisionAnalyzer: erro na otimizacao de imagens, '
                'usando originais — %s', str(e),
            )
            return screenshots

    # ------------------------------------------------------------------
    # Token tracking (9.3.2)
    # ------------------------------------------------------------------

    def _record_token_usage(
        self,
        execution_id: str,
        result: AnalysisResult,
        image_count: int,
    ) -> None:
        """
        Registra uso de tokens no banco de dados via TokenTracker.

        Args:
            execution_id: ID da execucao (UUID como string).
            result: Resultado da analise com dados de tokens.
            image_count: Numero de imagens enviadas.
        """
        try:
            from app.modules.agents.token_tracker import TokenTracker

            TokenTracker.record_usage(
                execution_id=execution_id,
                provider=self._provider_name,
                model=self._model,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                image_count=image_count,
            )
        except Exception as e:
            logger.warning(
                'VisionAnalyzer: erro ao registrar uso de tokens — %s',
                str(e),
            )

    # ------------------------------------------------------------------
    # Budget control (9.3.4)
    # ------------------------------------------------------------------

    @staticmethod
    def _check_token_budget() -> None:
        """
        Verifica se o budget diario/mensal de tokens foi excedido.

        Busca limites das Settings e compara com uso acumulado na
        tabela token_usage. Levanta excecao se excedido, loga
        warning quando atingir 80%.

        Raises:
            RuntimeError: Se budget diario ou mensal excedido.
        """
        try:
            from app.database import SessionLocal
            from app.modules.agents.token_tracker import TokenTracker
            from app.modules.settings.repository import SettingRepository
            from app.shared.utils import decrypt_value, utc_now

            db = SessionLocal()
            try:
                setting_repo = SettingRepository(db)

                # Busca limites configurados
                daily_limit_setting = setting_repo.get_by_key(
                    'token_budget.daily_limit',
                )
                monthly_limit_setting = setting_repo.get_by_key(
                    'token_budget.monthly_limit',
                )

                # Se nenhum limite configurado, nao faz verificacao
                if not daily_limit_setting and not monthly_limit_setting:
                    return

                now = utc_now()

                # Verifica limite diario
                if daily_limit_setting:
                    try:
                        daily_limit = int(
                            decrypt_value(daily_limit_setting.encrypted_value),
                        )
                    except (ValueError, Exception):
                        daily_limit = 0

                    if daily_limit > 0:
                        today_start = now.replace(
                            hour=0, minute=0, second=0, microsecond=0,
                        )
                        daily_used = TokenTracker.get_total_tokens_for_period(
                            date_from=today_start, date_to=now,
                        )

                        if daily_used >= daily_limit:
                            raise RuntimeError(
                                f'Budget de tokens diario excedido. '
                                f'Limite: {daily_limit:,}, Usado: {daily_used:,}'
                            )

                        usage_pct = (daily_used / daily_limit) * 100
                        if usage_pct >= 80:
                            logger.warning(
                                'VisionAnalyzer: budget diario em %.0f%% '
                                '(%d/%d tokens)',
                                usage_pct, daily_used, daily_limit,
                            )

                # Verifica limite mensal
                if monthly_limit_setting:
                    try:
                        monthly_limit = int(
                            decrypt_value(monthly_limit_setting.encrypted_value),
                        )
                    except (ValueError, Exception):
                        monthly_limit = 0

                    if monthly_limit > 0:
                        month_start = now.replace(
                            day=1, hour=0, minute=0, second=0, microsecond=0,
                        )
                        monthly_used = TokenTracker.get_total_tokens_for_period(
                            date_from=month_start, date_to=now,
                        )

                        if monthly_used >= monthly_limit:
                            raise RuntimeError(
                                f'Budget de tokens mensal excedido. '
                                f'Limite: {monthly_limit:,}, Usado: {monthly_used:,}'
                            )

                        usage_pct = (monthly_used / monthly_limit) * 100
                        if usage_pct >= 80:
                            logger.warning(
                                'VisionAnalyzer: budget mensal em %.0f%% '
                                '(%d/%d tokens)',
                                usage_pct, monthly_used, monthly_limit,
                            )

            finally:
                db.close()

        except RuntimeError:
            # Re-levanta erros de budget para o chamador tratar
            raise
        except Exception as e:
            # Erros na verificacao de budget nao devem bloquear a analise
            logger.debug(
                'VisionAnalyzer: erro ao verificar budget (continuando) — %s',
                str(e),
            )
