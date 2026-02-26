import hashlib
import json
import logging
import re
from datetime import datetime, timezone

from app.modules.agents.llm_provider import AnalysisResult, get_llm_provider
from app.modules.agents.llm_resilience import (
    LLMFallbackChain,
    circuit_breaker,
)

logger = logging.getLogger(__name__)

# Prompt compacto (~200 tokens) que instrui o LLM a retornar analise estruturada.
# Reduzido de ~500 tokens para economizar consumo sem perder instrucoes essenciais.
_SYSTEM_PROMPT_TEMPLATE = '''Analise as {num_screenshots} screenshots de paginas web.

Contexto:
{context}

Instrucoes:
{user_prompt}

{custom_instructions}Responda em DUAS partes:

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
```{schema_instructions}'''

# Template para instrucoes de schema enforcement (13.2.2)
_SCHEMA_ENFORCEMENT_TEMPLATE = '''

IMPORTANTE: O campo "extracted_fields" DEVE seguir EXATAMENTE este schema JSON:
{schema}

Retorne os dados no formato especificado. Campos obrigatorios nao podem ser omitidos.'''

# Template para correcao de schema (13.2.2)
_SCHEMA_CORRECTION_PROMPT = '''Sua resposta anterior nao seguiu o schema esperado.
Erros encontrados: {errors}

Corrija os dados JSON para seguir EXATAMENTE este schema:
{schema}

Retorne APENAS o JSON corrigido, sem texto adicional.'''

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
        fallback_providers: list[dict] | None = None,
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
            fallback_providers: Lista de configs de providers de fallback (13.1.2).
                                Cada dict contem: provider, api_key, model.
        """
        self._provider_name = provider_name
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout = timeout
        self._fallback_providers = fallback_providers or []
        self._actual_provider_used: str | None = None

        logger.info(
            'Inicializando VisionAnalyzer com provedor %s (modelo: %s, '
            'fallbacks: %d)',
            provider_name,
            model,
            len(self._fallback_providers),
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

        # Config primaria para uso com fallback chain
        self._primary_config = {
            'provider': provider_name,
            'api_key': api_key,
            'model': model,
            'temperature': temperature,
            'max_tokens': max_tokens,
            'timeout': timeout,
        }

    @property
    def actual_provider_used(self) -> str | None:
        """Retorna o nome do provider que realmente atendeu a ultima chamada."""
        return self._actual_provider_used

    @classmethod
    def from_llm_config(cls, llm_config: dict) -> 'VisionAnalyzer':
        """
        Cria uma instancia do VisionAnalyzer a partir de um dicionario de configuracao LLM.

        Metodo de conveniencia que aceita o mesmo formato retornado por
        ProjectService.get_llm_config().

        Args:
            llm_config: Dicionario com configuracoes do LLM contendo as chaves:
                        provider, api_key, model, temperature, max_tokens, timeout.
                        Opcionalmente: fallback_providers (lista de dicts).

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
            fallback_providers=llm_config.get('fallback_providers'),
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
            # 5. Envia para o provedor LLM (com fallback e circuit breaker)
            # ---------------------------------------------------------------
            result = self._call_llm_with_resilience(
                optimized_screenshots, full_prompt,
            )

            # ---------------------------------------------------------------
            # 5b. Validar schema dos dados extraidos (13.2.2)
            # ---------------------------------------------------------------
            expected_schema = (metadata or {}).get('expected_schema')
            if expected_schema and result.extracted_data:
                result = self._validate_and_correct_schema(
                    result, expected_schema, optimized_screenshots, full_prompt,
                )

            # ---------------------------------------------------------------
            # 5c. Comparar com analise anterior (13.2.4)
            # ---------------------------------------------------------------
            job_id = (metadata or {}).get('job_id')
            if job_id and result.extracted_data:
                changes = self._compare_with_previous(
                    job_id, result.extracted_data,
                )
                if changes:
                    result.extracted_data['_changes_detected'] = changes
                    logger.info(
                        'VisionAnalyzer: %d mudanca(s) detectada(s) vs '
                        'execucao anterior',
                        len(changes),
                    )

            logger.info(
                'VisionAnalyzer: analise concluida. Tokens usados: %d '
                '(in=%d, out=%d), Dados extraidos: %s, Provider: %s',
                result.tokens_used,
                result.input_tokens,
                result.output_tokens,
                'sim' if result.extracted_data else 'nao',
                self._actual_provider_used or self._provider_name,
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

        Combina o template de sistema com o prompt do usuario, metadados de contexto,
        instrucoes customizadas (13.2.1) e instrucoes de schema (13.2.2).

        Args:
            user_prompt: Prompt de analise do usuario/job.
            num_screenshots: Numero de screenshots sendo analisados.
            metadata: Metadados opcionais para contexto.

        Returns:
            Prompt completo formatado.
        """
        metadata = metadata or {}

        # Monta a secao de contexto com metadados
        context_parts: list[str] = []

        if metadata.get('project_name'):
            context_parts.append(f'Projeto: {metadata["project_name"]}')
        if metadata.get('job_name'):
            context_parts.append(f'Job: {metadata["job_name"]}')
        if metadata.get('base_url'):
            context_parts.append(f'URL base: {metadata["base_url"]}')
        if metadata.get('execution_id'):
            context_parts.append(f'ID da execucao: {metadata["execution_id"]}')

        context_parts.append(f'Screenshots analisados: {num_screenshots}')

        now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')
        context_parts.append(f'Data/hora da analise: {now_str}')

        context = '\n'.join(f'- {part}' for part in context_parts)

        # (13.2.1) System prompt customizavel por job
        custom_instructions = ''
        custom_prompt = metadata.get('custom_system_prompt', '')
        if custom_prompt:
            # Substitui variaveis de template
            custom_prompt = self._render_template_vars(custom_prompt, metadata)
            custom_instructions = f'Instrucoes adicionais:\n{custom_prompt}\n\n'

        # (13.2.2) Schema enforcement
        schema_instructions = ''
        expected_schema = metadata.get('expected_schema')
        if expected_schema:
            schema_json = json.dumps(expected_schema, indent=2, ensure_ascii=False)
            schema_instructions = _SCHEMA_ENFORCEMENT_TEMPLATE.format(
                schema=schema_json,
            )

        # Formata o prompt completo usando o template compacto
        full_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
            context=context,
            user_prompt=user_prompt,
            num_screenshots=num_screenshots,
            custom_instructions=custom_instructions,
            schema_instructions=schema_instructions,
        )

        return full_prompt

    @staticmethod
    def _render_template_vars(template: str, metadata: dict) -> str:
        """
        Substitui variaveis de template no prompt customizado (13.2.1).

        Variaveis suportadas: {{project_name}}, {{job_name}}, {{url}}, {{date}}.

        Args:
            template: Texto com variaveis de template.
            metadata: Metadados para substituicao.

        Returns:
            Texto com variaveis substituidas.
        """
        now_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        replacements = {
            '{{project_name}}': metadata.get('project_name', ''),
            '{{job_name}}': metadata.get('job_name', ''),
            '{{url}}': metadata.get('base_url', ''),
            '{{date}}': now_str,
        }
        result = template
        for var, value in replacements.items():
            result = result.replace(var, str(value))
        return result

    # ------------------------------------------------------------------
    # LLM call com resiliencia (13.1.1, 13.1.2, 13.1.3)
    # ------------------------------------------------------------------

    def _call_llm_with_resilience(
        self,
        screenshots: list[bytes],
        prompt: str,
    ) -> AnalysisResult:
        """
        Executa chamada LLM com circuit breaker e fallback entre providers.

        Se o provider primario estiver com circuito aberto ou falhar apos
        retries (tratados dentro do provider via @retry_with_backoff),
        tenta os fallback providers na ordem configurada.

        Args:
            screenshots: Lista de screenshots otimizados.
            prompt: Prompt completo para analise.

        Returns:
            AnalysisResult da chamada bem-sucedida.
        """
        # Se nao ha fallback configurado, usa chamada direta com circuit breaker
        if not self._fallback_providers:
            return self._call_single_provider(
                self._provider, self._provider_name, screenshots, prompt,
            )

        # Com fallback: usa LLMFallbackChain
        def _do_call(provider, imgs, p):
            if len(imgs) == 1:
                return provider.analyze_image(image_data=imgs[0], prompt=p)
            return provider.analyze_images(images=imgs, prompt=p)

        chain = LLMFallbackChain(
            primary_config=self._primary_config,
            fallback_configs=self._fallback_providers,
        )

        try:
            result = chain.execute(_do_call, screenshots, prompt)
            self._actual_provider_used = chain.actual_provider_used
            return result
        except Exception:
            # Se todos os providers falharem, retorna resultado de erro
            self._actual_provider_used = self._provider_name
            return AnalysisResult(
                text=(
                    f'Todos os providers LLM falharam '
                    f'(primario: {self._provider_name}, '
                    f'fallbacks: {len(self._fallback_providers)})'
                ),
                extracted_data=None,
                tokens_used=0,
            )

    def _call_single_provider(
        self,
        provider,
        provider_name: str,
        screenshots: list[bytes],
        prompt: str,
    ) -> AnalysisResult:
        """
        Executa chamada a um unico provider com integracao do circuit breaker.

        Args:
            provider: Instancia do provider LLM.
            provider_name: Nome do provider.
            screenshots: Lista de screenshots.
            prompt: Prompt completo.

        Returns:
            AnalysisResult da chamada.
        """
        # Verifica circuit breaker
        if not circuit_breaker.is_available(provider_name):
            logger.warning(
                'VisionAnalyzer: provider %s com circuit breaker aberto',
                provider_name,
            )
            return AnalysisResult(
                text=(
                    f'Provider {provider_name} temporariamente '
                    f'indisponivel (circuit breaker aberto)'
                ),
                extracted_data=None,
                tokens_used=0,
            )

        try:
            if len(screenshots) == 1:
                result = provider.analyze_image(
                    image_data=screenshots[0], prompt=prompt,
                )
            else:
                result = provider.analyze_images(
                    images=screenshots, prompt=prompt,
                )

            # Sucesso: registra no circuit breaker
            circuit_breaker.record_success(provider_name)
            self._actual_provider_used = provider_name
            return result

        except Exception as e:
            # Falha: registra no circuit breaker
            circuit_breaker.record_failure(provider_name)
            logger.error(
                'VisionAnalyzer: provider %s falhou — %s',
                provider_name, str(e),
            )
            self._actual_provider_used = provider_name
            return AnalysisResult(
                text=f'Erro na analise com {provider_name}: {str(e)}',
                extracted_data=None,
                tokens_used=0,
            )

    # ------------------------------------------------------------------
    # Schema enforcement (13.2.2)
    # ------------------------------------------------------------------

    def _validate_and_correct_schema(
        self,
        result: AnalysisResult,
        expected_schema: dict,
        screenshots: list[bytes],
        original_prompt: str,
    ) -> AnalysisResult:
        """
        Valida os dados extraidos contra o schema esperado e tenta corrigir.

        Se a validacao falhar, reenvia ao LLM com instrucoes de correcao.
        Maximo de 1 tentativa de correcao para nao gastar muitos tokens.

        Args:
            result: Resultado original da analise.
            expected_schema: JSON Schema esperado.
            screenshots: Screenshots para reenvio se necessario.
            original_prompt: Prompt original.

        Returns:
            AnalysisResult com dados corrigidos ou original se nao necessario.
        """
        errors = self._validate_json_schema(
            result.extracted_data, expected_schema,
        )
        if not errors:
            return result

        logger.warning(
            'VisionAnalyzer: dados extraidos nao seguem o schema. '
            'Erros: %s. Tentando correcao.',
            errors,
        )

        # Tenta correcao com um prompt de correcao
        try:
            correction_prompt = _SCHEMA_CORRECTION_PROMPT.format(
                errors='; '.join(errors),
                schema=json.dumps(expected_schema, indent=2, ensure_ascii=False),
            )

            # Adiciona os dados errados como contexto
            data_str = json.dumps(
                result.extracted_data, indent=2, ensure_ascii=False,
            )
            correction_prompt += f'\n\nDados originais:\n```json\n{data_str}\n```'

            correction_result = self._call_llm_with_resilience(
                screenshots[:1], correction_prompt,
            )

            if correction_result.extracted_data:
                new_errors = self._validate_json_schema(
                    correction_result.extracted_data, expected_schema,
                )
                if not new_errors:
                    logger.info(
                        'VisionAnalyzer: correcao de schema bem-sucedida',
                    )
                    # Soma tokens da correcao
                    return AnalysisResult(
                        text=result.text,
                        extracted_data=correction_result.extracted_data,
                        tokens_used=result.tokens_used + correction_result.tokens_used,
                        input_tokens=result.input_tokens + correction_result.input_tokens,
                        output_tokens=result.output_tokens + correction_result.output_tokens,
                    )

            logger.warning(
                'VisionAnalyzer: correcao de schema falhou, '
                'retornando dados originais',
            )
        except Exception as e:
            logger.warning(
                'VisionAnalyzer: erro na correcao de schema — %s', str(e),
            )

        return result

    @staticmethod
    def _validate_json_schema(data: dict, schema: dict) -> list[str]:
        """
        Valida dados contra um JSON Schema.

        Implementacao simplificada que verifica campos obrigatorios e tipos.
        Nao depende de jsonschema lib para manter lightweight.

        Args:
            data: Dados a validar.
            schema: JSON Schema com 'required' e 'properties'.

        Returns:
            Lista de erros encontrados (vazia se tudo OK).
        """
        errors: list[str] = []

        if not isinstance(data, dict) or not isinstance(schema, dict):
            return errors

        # Valida campos obrigatorios
        required_fields = schema.get('required', [])
        extracted = data.get('extracted_fields', data)

        for field in required_fields:
            if field not in extracted:
                errors.append(f'Campo obrigatorio ausente: {field}')

        # Valida tipos basicos se 'properties' estiver definido
        properties = schema.get('properties', {})
        type_map = {
            'string': str, 'number': (int, float), 'integer': int,
            'boolean': bool, 'array': list, 'object': dict,
        }

        for field_name, field_schema in properties.items():
            if field_name not in extracted:
                continue
            expected_type = field_schema.get('type')
            if expected_type and expected_type in type_map:
                if not isinstance(extracted[field_name], type_map[expected_type]):
                    errors.append(
                        f'Campo "{field_name}": esperado {expected_type}, '
                        f'recebido {type(extracted[field_name]).__name__}'
                    )

        return errors

    # ------------------------------------------------------------------
    # Comparacao de analises (13.2.4)
    # ------------------------------------------------------------------

    @staticmethod
    def _compare_with_previous(
        job_id: str,
        current_data: dict,
    ) -> list[dict] | None:
        """
        Compara a analise atual com a analise anterior do mesmo job.

        Detecta mudancas significativas nos campos extraidos.

        Args:
            job_id: ID do job.
            current_data: Dados extraidos da analise atual.

        Returns:
            Lista de mudancas detectadas ou None se nao houver anterior.
        """
        try:
            from app.database import SessionLocal
            from app.modules.executions.models import Execution

            db = SessionLocal()
            try:
                # Busca a ultima execucao com sucesso do mesmo job
                previous = (
                    db.query(Execution)
                    .filter(
                        Execution.job_id == job_id,
                        Execution.status == 'success',
                        Execution.extracted_data.isnot(None),
                    )
                    .order_by(Execution.created_at.desc())
                    .first()
                )

                if not previous or not previous.extracted_data:
                    return None

                prev_data = previous.extracted_data
                if isinstance(prev_data, str):
                    try:
                        prev_data = json.loads(prev_data)
                    except (json.JSONDecodeError, ValueError):
                        return None

                if not isinstance(prev_data, dict):
                    return None

                # Compara campos-chave
                changes: list[dict] = []

                # Compara campos de extracted_fields
                prev_fields = prev_data.get('extracted_fields', {})
                curr_fields = current_data.get('extracted_fields', {})

                if isinstance(prev_fields, dict) and isinstance(curr_fields, dict):
                    all_keys = set(prev_fields.keys()) | set(curr_fields.keys())
                    for key in all_keys:
                        old_val = prev_fields.get(key)
                        new_val = curr_fields.get(key)
                        if old_val != new_val:
                            changes.append({
                                'field': key,
                                'old_value': str(old_val) if old_val is not None else None,
                                'new_value': str(new_val) if new_val is not None else None,
                                'type': 'modified' if key in prev_fields and key in curr_fields
                                        else 'added' if key not in prev_fields
                                        else 'removed',
                            })

                # Compara summary
                prev_summary = prev_data.get('summary', '')
                curr_summary = current_data.get('summary', '')
                if prev_summary and curr_summary and prev_summary != curr_summary:
                    changes.append({
                        'field': 'summary',
                        'old_value': prev_summary[:200],
                        'new_value': curr_summary[:200],
                        'type': 'modified',
                    })

                # Compara status
                prev_status = prev_data.get('status', '')
                curr_status = current_data.get('status', '')
                if prev_status and curr_status and prev_status != curr_status:
                    changes.append({
                        'field': 'status',
                        'old_value': prev_status,
                        'new_value': curr_status,
                        'type': 'modified',
                    })

                if changes:
                    logger.info(
                        'VisionAnalyzer: MUDANCAS DETECTADAS para job %s: %s',
                        job_id,
                        '; '.join(
                            f'{c["field"]}: {c["old_value"]} -> {c["new_value"]}'
                            for c in changes[:5]
                        ),
                    )

                return changes if changes else None

            finally:
                db.close()

        except Exception as e:
            logger.debug(
                'VisionAnalyzer: erro na comparacao de analises — %s',
                str(e),
            )
            return None

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
