import logging
from datetime import datetime, timezone

from app.modules.agents.llm_provider import AnalysisResult, get_llm_provider

logger = logging.getLogger(__name__)

# Prompt de sistema que instrui o LLM a retornar analise estruturada
_SYSTEM_PROMPT_TEMPLATE = '''Voce e um analisador visual especializado. Sua tarefa e analisar screenshots de paginas web
e extrair informacoes relevantes de forma estruturada.

## Contexto
{context}

## Instrucoes de Analise
{user_prompt}

## Formato de Resposta Esperado

Forneca sua resposta em DUAS partes:

### PARTE 1 - Analise Textual
Escreva uma analise detalhada das screenshots, incluindo:
- Descricao do conteudo visual identificado
- Informacoes relevantes encontradas
- Observacoes e insights importantes
- Status geral da pagina/aplicacao observada

### PARTE 2 - Dados Estruturados
Ao final da sua resposta, inclua um bloco JSON com os dados extraidos no seguinte formato:

```json
{{
    "title": "Titulo ou assunto principal identificado",
    "summary": "Resumo conciso das informacoes encontradas",
    "extracted_fields": {{
        "campo1": "valor1",
        "campo2": "valor2"
    }},
    "insights": [
        "Insight ou observacao relevante 1",
        "Insight ou observacao relevante 2"
    ],
    "status": "success|partial|error",
    "confidence": 0.0,
    "screenshots_analyzed": {num_screenshots},
    "timestamp": "{timestamp}"
}}
```

Preencha os campos com as informacoes reais extraidas das screenshots.
O campo "extracted_fields" deve conter pares chave-valor com os dados especificos solicitados.
O campo "confidence" deve ser um valor entre 0.0 e 1.0 indicando sua confianca na analise.
O campo "status" deve ser "success" se todos os dados foram extraidos, "partial" se apenas parte, ou "error" se houve problemas.'''


class VisionAnalyzer:
    """
    Analisador visual que utiliza provedores LLM para extrair informacoes de screenshots.

    Recebe screenshots em bytes e um prompt de analise, constroi um prompt contextual
    abrangente e envia para o provedor LLM configurado para obter analise textual
    e dados estruturados (JSON).
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

        Constroi um prompt abrangente com contexto, instrucoes do usuario e
        formato de saida estruturada, envia as imagens para o LLM e retorna
        o resultado da analise.

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

            # Envia para o provedor LLM (single ou multi-image)
            if len(screenshots) == 1:
                result = self._provider.analyze_image(
                    image_data=screenshots[0],
                    prompt=full_prompt,
                )
            else:
                result = self._provider.analyze_images(
                    images=screenshots,
                    prompt=full_prompt,
                )

            logger.info(
                'VisionAnalyzer: analise concluida. Tokens usados: %d, '
                'Dados extraidos: %s',
                result.tokens_used,
                'sim' if result.extracted_data else 'nao',
            )

            return result

        except Exception as e:
            error_msg = f'Erro na analise visual com {self._provider_name}: {str(e)}'
            logger.error('VisionAnalyzer: %s', error_msg)
            return AnalysisResult(
                text=error_msg,
                extracted_data=None,
                tokens_used=0,
            )

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

        # Gera timestamp para o template JSON
        timestamp = datetime.now(timezone.utc).isoformat()

        # Formata o prompt completo usando o template
        full_prompt = _SYSTEM_PROMPT_TEMPLATE.format(
            context=context,
            user_prompt=user_prompt,
            num_screenshots=num_screenshots,
            timestamp=timestamp,
        )

        return full_prompt
