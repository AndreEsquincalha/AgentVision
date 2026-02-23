import base64
import json
import logging
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """Resultado da analise de imagem(ns) por um provedor LLM."""

    text: str
    extracted_data: dict | None = field(default=None)
    tokens_used: int = 0


class BaseLLMProvider(ABC):
    """
    Classe base abstrata para provedores de LLM com capacidade de visao.

    Define a interface que todos os provedores devem implementar para
    analise de imagens (single e multi-image).
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: int = 120,
    ) -> None:
        """
        Inicializa o provedor LLM.

        Args:
            api_key: Chave de API do provedor.
            model: Nome do modelo a ser utilizado.
            temperature: Temperatura para geracao (0.0 a 2.0).
            max_tokens: Numero maximo de tokens na resposta.
            timeout: Timeout em segundos para chamadas a API.
        """
        self._api_key = api_key
        self._model = model
        self._temperature = temperature
        self._max_tokens = max_tokens
        self._timeout = timeout

    @abstractmethod
    def analyze_image(self, image_data: bytes, prompt: str) -> AnalysisResult:
        """
        Analisa uma unica imagem com o provedor LLM.

        Args:
            image_data: Dados da imagem em bytes (PNG/JPEG).
            prompt: Prompt de instrucao para a analise.

        Returns:
            Resultado da analise contendo texto, dados extraidos e tokens usados.
        """
        ...

    @abstractmethod
    def analyze_images(self, images: list[bytes], prompt: str) -> AnalysisResult:
        """
        Analisa multiplas imagens com o provedor LLM.

        Args:
            images: Lista de imagens em bytes (PNG/JPEG).
            prompt: Prompt de instrucao para a analise.

        Returns:
            Resultado da analise contendo texto, dados extraidos e tokens usados.
        """
        ...

    def _extract_json_from_text(self, text: str) -> dict | None:
        """
        Tenta extrair dados JSON de um texto de resposta do LLM.

        Procura por blocos de codigo JSON (```json ... ```) ou objetos JSON
        diretamente no texto.

        Args:
            text: Texto completo da resposta do LLM.

        Returns:
            Dicionario com os dados extraidos ou None se nao encontrar JSON valido.
        """
        # Tenta extrair JSON de blocos de codigo markdown
        json_block_pattern = r'```(?:json)?\s*\n?([\s\S]*?)\n?```'
        matches = re.findall(json_block_pattern, text)
        for match in matches:
            try:
                parsed = json.loads(match.strip())
                if isinstance(parsed, dict):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                continue

        # Tenta encontrar um objeto JSON no texto
        brace_pattern = r'\{[\s\S]*\}'
        brace_matches = re.findall(brace_pattern, text)
        for match in brace_matches:
            try:
                parsed = json.loads(match.strip())
                if isinstance(parsed, dict):
                    return parsed
            except (json.JSONDecodeError, ValueError):
                continue

        return None

    @staticmethod
    def _encode_image_base64(image_data: bytes) -> str:
        """Codifica imagem em base64."""
        return base64.b64encode(image_data).decode('utf-8')

    @staticmethod
    def _detect_media_type(image_data: bytes) -> str:
        """
        Detecta o tipo MIME da imagem com base nos bytes iniciais (magic bytes).

        Args:
            image_data: Dados da imagem em bytes.

        Returns:
            Tipo MIME da imagem (image/png, image/jpeg, image/gif ou image/webp).
        """
        if image_data[:8] == b'\x89PNG\r\n\x1a\n':
            return 'image/png'
        elif image_data[:2] == b'\xff\xd8':
            return 'image/jpeg'
        elif image_data[:4] == b'GIF8':
            return 'image/gif'
        elif image_data[:4] == b'RIFF' and image_data[8:12] == b'WEBP':
            return 'image/webp'
        # Padrao para PNG se nao conseguir detectar
        return 'image/png'


class AnthropicProvider(BaseLLMProvider):
    """
    Provedor LLM usando a API da Anthropic (Claude Vision).

    Utiliza o SDK anthropic para enviar imagens codificadas em base64
    e obter analise visual via modelos Claude.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: int = 120,
    ) -> None:
        super().__init__(api_key, model, temperature, max_tokens, timeout)
        try:
            from anthropic import Anthropic
            self._client = Anthropic(
                api_key=self._api_key,
                timeout=float(self._timeout),
            )
        except ImportError:
            raise ImportError(
                'O pacote "anthropic" e necessario para usar o AnthropicProvider. '
                'Instale com: pip install anthropic'
            )

    def analyze_image(self, image_data: bytes, prompt: str) -> AnalysisResult:
        """Analisa uma unica imagem usando Claude Vision."""
        return self.analyze_images([image_data], prompt)

    def analyze_images(self, images: list[bytes], prompt: str) -> AnalysisResult:
        """Analisa multiplas imagens usando Claude Vision."""
        logger.info(
            'AnthropicProvider: analisando %d imagem(ns) com modelo %s',
            len(images),
            self._model,
        )

        try:
            # Monta o conteudo da mensagem com texto e imagens
            content: list[dict] = [
                {'type': 'text', 'text': prompt},
            ]

            for image_data in images:
                b64_data = self._encode_image_base64(image_data)
                media_type = self._detect_media_type(image_data)
                content.append({
                    'type': 'image',
                    'source': {
                        'type': 'base64',
                        'media_type': media_type,
                        'data': b64_data,
                    },
                })

            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                messages=[
                    {
                        'role': 'user',
                        'content': content,
                    },
                ],
            )

            # Extrai texto da resposta
            response_text = ''
            for block in response.content:
                if hasattr(block, 'text'):
                    response_text += block.text

            # Calcula tokens usados
            tokens_used = 0
            if hasattr(response, 'usage'):
                tokens_used = (
                    getattr(response.usage, 'input_tokens', 0)
                    + getattr(response.usage, 'output_tokens', 0)
                )

            # Tenta extrair JSON da resposta
            extracted_data = self._extract_json_from_text(response_text)

            logger.info(
                'AnthropicProvider: analise concluida. Tokens usados: %d',
                tokens_used,
            )

            return AnalysisResult(
                text=response_text,
                extracted_data=extracted_data,
                tokens_used=tokens_used,
            )

        except Exception as e:
            logger.error('AnthropicProvider: erro na analise - %s', str(e))
            return AnalysisResult(
                text=f'Erro na analise com Anthropic: {str(e)}',
                extracted_data=None,
                tokens_used=0,
            )


class OpenAIProvider(BaseLLMProvider):
    """
    Provedor LLM usando a API da OpenAI (GPT-4o Vision).

    Utiliza o SDK openai para enviar imagens como data URLs base64
    e obter analise visual via modelos GPT-4o.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: int = 120,
    ) -> None:
        super().__init__(api_key, model, temperature, max_tokens, timeout)
        try:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=self._api_key,
                timeout=float(self._timeout),
            )
        except ImportError:
            raise ImportError(
                'O pacote "openai" e necessario para usar o OpenAIProvider. '
                'Instale com: pip install openai'
            )

    def analyze_image(self, image_data: bytes, prompt: str) -> AnalysisResult:
        """Analisa uma unica imagem usando GPT-4o Vision."""
        return self.analyze_images([image_data], prompt)

    def analyze_images(self, images: list[bytes], prompt: str) -> AnalysisResult:
        """Analisa multiplas imagens usando GPT-4o Vision."""
        logger.info(
            'OpenAIProvider: analisando %d imagem(ns) com modelo %s',
            len(images),
            self._model,
        )

        try:
            # Monta o conteudo da mensagem com texto e imagens
            content: list[dict] = [
                {'type': 'text', 'text': prompt},
            ]

            for image_data in images:
                b64_data = self._encode_image_base64(image_data)
                media_type = self._detect_media_type(image_data)
                data_url = f'data:{media_type};base64,{b64_data}'
                content.append({
                    'type': 'image_url',
                    'image_url': {
                        'url': data_url,
                        'detail': 'high',
                    },
                })

            response = self._client.chat.completions.create(
                model=self._model,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                messages=[
                    {
                        'role': 'user',
                        'content': content,
                    },
                ],
            )

            # Extrai texto da resposta
            response_text = ''
            if response.choices and response.choices[0].message.content:
                response_text = response.choices[0].message.content

            # Calcula tokens usados
            tokens_used = 0
            if response.usage:
                tokens_used = (
                    getattr(response.usage, 'prompt_tokens', 0)
                    + getattr(response.usage, 'completion_tokens', 0)
                )

            # Tenta extrair JSON da resposta
            extracted_data = self._extract_json_from_text(response_text)

            logger.info(
                'OpenAIProvider: analise concluida. Tokens usados: %d',
                tokens_used,
            )

            return AnalysisResult(
                text=response_text,
                extracted_data=extracted_data,
                tokens_used=tokens_used,
            )

        except Exception as e:
            logger.error('OpenAIProvider: erro na analise - %s', str(e))
            return AnalysisResult(
                text=f'Erro na analise com OpenAI: {str(e)}',
                extracted_data=None,
                tokens_used=0,
            )


class GoogleProvider(BaseLLMProvider):
    """
    Provedor LLM usando a API do Google Gemini (Gemini Vision).

    Utiliza o SDK google-generativeai para enviar imagens em bytes
    e obter analise visual via modelos Gemini.
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: int = 120,
    ) -> None:
        super().__init__(api_key, model, temperature, max_tokens, timeout)
        try:
            import google.generativeai as genai
            genai.configure(api_key=self._api_key)
            self._genai = genai
            self._gen_model = genai.GenerativeModel(
                model_name=self._model,
                generation_config=genai.types.GenerationConfig(
                    temperature=self._temperature,
                    max_output_tokens=self._max_tokens,
                ),
            )
        except ImportError:
            raise ImportError(
                'O pacote "google-generativeai" e necessario para usar o GoogleProvider. '
                'Instale com: pip install google-generativeai'
            )

    def analyze_image(self, image_data: bytes, prompt: str) -> AnalysisResult:
        """Analisa uma unica imagem usando Gemini Vision."""
        return self.analyze_images([image_data], prompt)

    def analyze_images(self, images: list[bytes], prompt: str) -> AnalysisResult:
        """Analisa multiplas imagens usando Gemini Vision."""
        logger.info(
            'GoogleProvider: analisando %d imagem(ns) com modelo %s',
            len(images),
            self._model,
        )

        try:
            # Monta o conteudo com texto e imagens como partes inline
            contents: list = [prompt]

            for image_data in images:
                media_type = self._detect_media_type(image_data)
                contents.append({
                    'mime_type': media_type,
                    'data': image_data,
                })

            response = self._gen_model.generate_content(
                contents,
                request_options={'timeout': self._timeout},
            )

            # Extrai texto da resposta
            response_text = ''
            if response and response.text:
                response_text = response.text

            # Calcula tokens usados
            tokens_used = 0
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                tokens_used = (
                    getattr(response.usage_metadata, 'prompt_token_count', 0)
                    + getattr(response.usage_metadata, 'candidates_token_count', 0)
                )

            # Tenta extrair JSON da resposta
            extracted_data = self._extract_json_from_text(response_text)

            logger.info(
                'GoogleProvider: analise concluida. Tokens usados: %d',
                tokens_used,
            )

            return AnalysisResult(
                text=response_text,
                extracted_data=extracted_data,
                tokens_used=tokens_used,
            )

        except Exception as e:
            logger.error('GoogleProvider: erro na analise - %s', str(e))
            return AnalysisResult(
                text=f'Erro na analise com Google Gemini: {str(e)}',
                extracted_data=None,
                tokens_used=0,
            )


class OllamaProvider(BaseLLMProvider):
    """
    Provedor LLM usando a API local do Ollama.

    Utiliza requisicoes HTTP via httpx para enviar imagens codificadas
    em base64 para modelos locais com suporte a visao (llava, bakllava, etc).
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: int = 120,
    ) -> None:
        super().__init__(api_key, model, temperature, max_tokens, timeout)
        # Ollama nao requer API key, mas o parametro api_key pode conter
        # a URL base do servidor Ollama (ex: http://host:11434)
        if api_key and api_key.startswith('http'):
            self._base_url = api_key.rstrip('/')
        else:
            self._base_url = 'http://localhost:11434'

    def analyze_image(self, image_data: bytes, prompt: str) -> AnalysisResult:
        """Analisa uma unica imagem usando Ollama local."""
        return self.analyze_images([image_data], prompt)

    def analyze_images(self, images: list[bytes], prompt: str) -> AnalysisResult:
        """Analisa multiplas imagens usando Ollama local."""
        logger.info(
            'OllamaProvider: analisando %d imagem(ns) com modelo %s em %s',
            len(images),
            self._model,
            self._base_url,
        )

        try:
            # Codifica todas as imagens em base64
            b64_images = [self._encode_image_base64(img) for img in images]

            # Usa endpoint /api/chat para suporte a imagens
            payload = {
                'model': self._model,
                'messages': [
                    {
                        'role': 'user',
                        'content': prompt,
                        'images': b64_images,
                    },
                ],
                'stream': False,
                'options': {
                    'temperature': self._temperature,
                    'num_predict': self._max_tokens,
                },
            }

            with httpx.Client(timeout=float(self._timeout)) as client:
                response = client.post(
                    f'{self._base_url}/api/chat',
                    json=payload,
                )
                response.raise_for_status()

            data = response.json()

            # Extrai texto da resposta
            response_text = ''
            if 'message' in data and 'content' in data['message']:
                response_text = data['message']['content']

            # Calcula tokens usados (Ollama retorna em campos diferentes)
            tokens_used = 0
            if 'prompt_eval_count' in data:
                tokens_used += data['prompt_eval_count']
            if 'eval_count' in data:
                tokens_used += data['eval_count']

            # Tenta extrair JSON da resposta
            extracted_data = self._extract_json_from_text(response_text)

            logger.info(
                'OllamaProvider: analise concluida. Tokens usados: %d',
                tokens_used,
            )

            return AnalysisResult(
                text=response_text,
                extracted_data=extracted_data,
                tokens_used=tokens_used,
            )

        except httpx.ConnectError:
            error_msg = (
                f'Erro de conexao com Ollama em {self._base_url}. '
                'Verifique se o servidor Ollama esta em execucao.'
            )
            logger.error('OllamaProvider: %s', error_msg)
            return AnalysisResult(
                text=error_msg,
                extracted_data=None,
                tokens_used=0,
            )
        except Exception as e:
            logger.error('OllamaProvider: erro na analise - %s', str(e))
            return AnalysisResult(
                text=f'Erro na analise com Ollama: {str(e)}',
                extracted_data=None,
                tokens_used=0,
            )


# -------------------------------------------------------------------------
# Factory
# -------------------------------------------------------------------------

_PROVIDER_MAP: dict[str, type[BaseLLMProvider]] = {
    'anthropic': AnthropicProvider,
    'openai': OpenAIProvider,
    'google': GoogleProvider,
    'ollama': OllamaProvider,
}


def get_llm_provider(
    provider_name: str,
    api_key: str,
    model: str,
    temperature: float = 0.7,
    max_tokens: int = 4096,
    timeout: int = 120,
) -> BaseLLMProvider:
    """
    Factory function para instanciar o provedor LLM correto.

    Args:
        provider_name: Nome do provedor ('anthropic', 'openai', 'google', 'ollama').
        api_key: Chave de API do provedor (para Ollama, pode ser a URL base).
        model: Nome do modelo a ser utilizado.
        temperature: Temperatura para geracao (0.0 a 2.0).
        max_tokens: Numero maximo de tokens na resposta.
        timeout: Timeout em segundos para chamadas a API.

    Returns:
        Instancia do provedor LLM configurado.

    Raises:
        ValueError: Se o nome do provedor nao for reconhecido.
    """
    provider_class = _PROVIDER_MAP.get(provider_name.lower())

    if provider_class is None:
        valid_providers = ', '.join(sorted(_PROVIDER_MAP.keys()))
        raise ValueError(
            f'Provedor LLM "{provider_name}" nao reconhecido. '
            f'Provedores validos: {valid_providers}'
        )

    logger.info(
        'Criando provedor LLM: %s (modelo: %s, temperature: %.2f, max_tokens: %d)',
        provider_name,
        model,
        temperature,
        max_tokens,
    )

    return provider_class(
        api_key=api_key,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )
