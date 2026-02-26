import base64
import io
import json
import logging
import math
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

import httpx

from app.modules.agents.llm_resilience import retry_with_backoff

logger = logging.getLogger(__name__)


@dataclass
class AnalysisResult:
    """Resultado da analise de imagem(ns) por um provedor LLM."""

    text: str
    extracted_data: dict | None = field(default=None)
    tokens_used: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


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

    @property
    def provider_name(self) -> str:
        """Retorna o nome do provider para tracking/logging."""
        return self.__class__.__name__.replace('Provider', '').lower()

    @property
    def model_name(self) -> str:
        """Retorna o nome do modelo configurado."""
        return self._model

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

    def estimate_tokens(self, text: str, images: list[bytes]) -> dict[str, int]:
        """
        Estima o numero de tokens que serao consumidos pela chamada.

        Args:
            text: Texto do prompt completo.
            images: Lista de imagens em bytes.

        Returns:
            Dicionario com text_tokens, image_tokens, total e context_limit.
        """
        # Texto: ~4 chars = 1 token (PT-BR tem mais acentos)
        text_tokens = len(text) // 4

        # Imagens: varia por provider (subclasse pode sobrescrever)
        image_tokens = self._estimate_image_tokens(images)

        total = text_tokens + image_tokens
        return {
            'text_tokens': text_tokens,
            'image_tokens': image_tokens,
            'total': total,
            'context_limit': self._get_context_limit(),
        }

    def _estimate_image_tokens(self, images: list[bytes]) -> int:
        """
        Estimativa base de tokens por imagem. Override por provider.

        Args:
            images: Lista de imagens em bytes.

        Returns:
            Estimativa total de tokens de imagem.
        """
        return len(images) * 1000  # Estimativa conservadora padrao

    def _get_context_limit(self) -> int:
        """
        Retorna o limite de contexto do modelo. Override por provider.

        Returns:
            Limite de tokens de contexto.
        """
        return 128000  # Default seguro

    @staticmethod
    def _get_image_dimensions(image_data: bytes) -> tuple[int, int]:
        """
        Obtem dimensoes de uma imagem sem carrega-la completamente.

        Args:
            image_data: Bytes da imagem.

        Returns:
            Tupla (largura, altura). Retorna (1024, 768) como fallback.
        """
        try:
            from PIL import Image
            img = Image.open(io.BytesIO(image_data))
            return img.size
        except Exception:
            return (1024, 768)

    def analyze_images_structured(
        self,
        images: list[bytes],
        prompt: str,
        output_schema: dict | None = None,
    ) -> AnalysisResult:
        """
        Analisa imagens forcando saida JSON estruturada (13.2.3).

        Usa mecanismos nativos de cada provider (tool_use, response_format,
        response_schema) para garantir saida estruturada.
        Implementacao base: delega para analyze_images() com prompt enriquecido.
        Providers podem sobrescrever para usar mecanismos nativos.

        Args:
            images: Lista de imagens em bytes.
            prompt: Prompt de instrucao.
            output_schema: JSON Schema esperado para a saida.

        Returns:
            AnalysisResult com dados extraidos garantidamente em JSON.
        """
        # Implementacao base: enriquece prompt com instrucao de JSON
        enhanced_prompt = prompt
        if output_schema:
            schema_str = json.dumps(output_schema, indent=2, ensure_ascii=False)
            enhanced_prompt += (
                f'\n\nRETORNE APENAS um JSON valido seguindo este schema:\n'
                f'```json\n{schema_str}\n```'
            )
        return self.analyze_images(images, enhanced_prompt)

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

    # Limite maximo de output tokens para modelos Anthropic (64k para Sonnet/Opus)
    _MAX_OUTPUT_TOKENS = 64000

    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: int = 120,
    ) -> None:
        # Garante que max_tokens nao exceda o limite do provider
        max_tokens = min(max_tokens, self._MAX_OUTPUT_TOKENS)
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

    def _estimate_image_tokens(self, images: list[bytes]) -> int:
        """Anthropic: largura * altura / 750 tokens por imagem."""
        total = 0
        for img_bytes in images:
            w, h = self._get_image_dimensions(img_bytes)
            total += int(w * h / 750)
        return total

    def _get_context_limit(self) -> int:
        """Claude Sonnet/Opus suportam 200k de contexto."""
        return 200000

    def analyze_image(self, image_data: bytes, prompt: str) -> AnalysisResult:
        """Analisa uma unica imagem usando Claude Vision."""
        return self.analyze_images([image_data], prompt)

    def analyze_images_structured(
        self,
        images: list[bytes],
        prompt: str,
        output_schema: dict | None = None,
    ) -> AnalysisResult:
        """Anthropic: usa tool_use para forcar JSON estruturado (13.2.3)."""
        if not output_schema:
            return self.analyze_images(images, prompt)

        logger.info(
            'AnthropicProvider: analise estruturada com tool_use (%d imagens)',
            len(images),
        )

        try:
            content: list[dict] = [{'type': 'text', 'text': prompt}]
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

            # Define ferramenta que forca o schema de saida
            tool_def = {
                'name': 'extract_data',
                'description': 'Extrai dados estruturados das screenshots analisadas',
                'input_schema': output_schema,
            }

            response = self._client.messages.create(
                model=self._model,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                tools=[tool_def],
                tool_choice={'type': 'tool', 'name': 'extract_data'},
                messages=[{'role': 'user', 'content': content}],
            )

            # Extrai resultado do tool_use
            extracted_data = None
            response_text = ''
            for block in response.content:
                if hasattr(block, 'input'):
                    extracted_data = block.input
                elif hasattr(block, 'text'):
                    response_text += block.text

            input_tokens = getattr(response.usage, 'input_tokens', 0) if hasattr(response, 'usage') else 0
            output_tokens = getattr(response.usage, 'output_tokens', 0) if hasattr(response, 'usage') else 0

            return AnalysisResult(
                text=response_text or json.dumps(extracted_data or {}, ensure_ascii=False),
                extracted_data=extracted_data,
                tokens_used=input_tokens + output_tokens,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        except Exception as e:
            logger.warning(
                'AnthropicProvider: falha no tool_use, fallback para '
                'analyze_images — %s', str(e),
            )
            return super().analyze_images_structured(images, prompt, output_schema)

    @retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=30.0)
    def analyze_images(self, images: list[bytes], prompt: str) -> AnalysisResult:
        """Analisa multiplas imagens usando Claude Vision."""
        logger.info(
            'AnthropicProvider: analisando %d imagem(ns) com modelo %s',
            len(images),
            self._model,
        )

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

        # Calcula tokens usados (detalhado por input/output)
        input_tokens = 0
        output_tokens = 0
        if hasattr(response, 'usage'):
            input_tokens = getattr(response.usage, 'input_tokens', 0)
            output_tokens = getattr(response.usage, 'output_tokens', 0)
        tokens_used = input_tokens + output_tokens

        # Tenta extrair JSON da resposta
        extracted_data = self._extract_json_from_text(response_text)

        logger.info(
            'AnthropicProvider: analise concluida. Tokens usados: %d (in=%d, out=%d)',
            tokens_used, input_tokens, output_tokens,
        )

        return AnalysisResult(
            text=response_text,
            extracted_data=extracted_data,
            tokens_used=tokens_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


class OpenAIProvider(BaseLLMProvider):
    """
    Provedor LLM usando a API da OpenAI (GPT-4o Vision).

    Utiliza o SDK openai para enviar imagens como data URLs base64
    e obter analise visual via modelos GPT-4o.
    """

    _MAX_OUTPUT_TOKENS = 64000

    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: int = 120,
    ) -> None:
        max_tokens = min(max_tokens, self._MAX_OUTPUT_TOKENS)
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

    def _estimate_image_tokens(self, images: list[bytes]) -> int:
        """OpenAI: tiles de 512x512, cada tile ~170 tokens."""
        total = 0
        for img_bytes in images:
            w, h = self._get_image_dimensions(img_bytes)
            # Calcula numero de tiles 512x512 necessarios
            tiles_x = math.ceil(w / 512)
            tiles_y = math.ceil(h / 512)
            total += tiles_x * tiles_y * 170 + 85  # +85 base overhead
        return total

    def _get_context_limit(self) -> int:
        """GPT-4o suporta 128k de contexto."""
        return 128000

    def analyze_image(self, image_data: bytes, prompt: str) -> AnalysisResult:
        """Analisa uma unica imagem usando GPT-4o Vision."""
        return self.analyze_images([image_data], prompt)

    def analyze_images_structured(
        self,
        images: list[bytes],
        prompt: str,
        output_schema: dict | None = None,
    ) -> AnalysisResult:
        """OpenAI: usa response_format json_object para forcar JSON (13.2.3)."""
        if not output_schema:
            return self.analyze_images(images, prompt)

        logger.info(
            'OpenAIProvider: analise estruturada com json_object (%d imagens)',
            len(images),
        )

        try:
            content: list[dict] = [{'type': 'text', 'text': prompt}]
            for image_data in images:
                b64_data = self._encode_image_base64(image_data)
                media_type = self._detect_media_type(image_data)
                data_url = f'data:{media_type};base64,{b64_data}'
                content.append({
                    'type': 'image_url',
                    'image_url': {'url': data_url, 'detail': 'auto'},
                })

            # Enriquece prompt para instruir JSON + response_format
            schema_str = json.dumps(output_schema, indent=2, ensure_ascii=False)
            enhanced_prompt = (
                f'{prompt}\n\nRETORNE APENAS um JSON valido '
                f'seguindo este schema:\n{schema_str}'
            )
            content[0] = {'type': 'text', 'text': enhanced_prompt}

            response = self._client.chat.completions.create(
                model=self._model,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
                response_format={'type': 'json_object'},
                messages=[{'role': 'user', 'content': content}],
            )

            response_text = ''
            if response.choices and response.choices[0].message.content:
                response_text = response.choices[0].message.content

            extracted_data = self._extract_json_from_text(response_text)

            input_tokens = getattr(response.usage, 'prompt_tokens', 0) if response.usage else 0
            output_tokens = getattr(response.usage, 'completion_tokens', 0) if response.usage else 0

            return AnalysisResult(
                text=response_text,
                extracted_data=extracted_data,
                tokens_used=input_tokens + output_tokens,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        except Exception as e:
            logger.warning(
                'OpenAIProvider: falha no json_object, fallback — %s', str(e),
            )
            return super().analyze_images_structured(images, prompt, output_schema)

    @retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=30.0)
    def analyze_images(self, images: list[bytes], prompt: str) -> AnalysisResult:
        """Analisa multiplas imagens usando GPT-4o Vision."""
        logger.info(
            'OpenAIProvider: analisando %d imagem(ns) com modelo %s',
            len(images),
            self._model,
        )

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
                    'detail': 'auto',
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

        # Calcula tokens usados (detalhado por input/output)
        input_tokens = 0
        output_tokens = 0
        if response.usage:
            input_tokens = getattr(response.usage, 'prompt_tokens', 0)
            output_tokens = getattr(response.usage, 'completion_tokens', 0)
        tokens_used = input_tokens + output_tokens

        # Tenta extrair JSON da resposta
        extracted_data = self._extract_json_from_text(response_text)

        logger.info(
            'OpenAIProvider: analise concluida. Tokens usados: %d (in=%d, out=%d)',
            tokens_used, input_tokens, output_tokens,
        )

        return AnalysisResult(
            text=response_text,
            extracted_data=extracted_data,
            tokens_used=tokens_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
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

    def _estimate_image_tokens(self, images: list[bytes]) -> int:
        """Gemini: ~258 tokens por imagem."""
        return len(images) * 258

    def _get_context_limit(self) -> int:
        """Gemini 2.0 Flash suporta 1M+ de contexto, usamos 1M como limite."""
        return 1000000

    def analyze_image(self, image_data: bytes, prompt: str) -> AnalysisResult:
        """Analisa uma unica imagem usando Gemini Vision."""
        return self.analyze_images([image_data], prompt)

    def analyze_images_structured(
        self,
        images: list[bytes],
        prompt: str,
        output_schema: dict | None = None,
    ) -> AnalysisResult:
        """Google: usa response_mime_type json para forcar JSON (13.2.3)."""
        if not output_schema:
            return self.analyze_images(images, prompt)

        logger.info(
            'GoogleProvider: analise estruturada com response_mime_type (%d imagens)',
            len(images),
        )

        try:
            # Cria modelo com config de JSON output
            gen_config = self._genai.types.GenerationConfig(
                temperature=self._temperature,
                max_output_tokens=self._max_tokens,
                response_mime_type='application/json',
            )
            json_model = self._genai.GenerativeModel(
                model_name=self._model,
                generation_config=gen_config,
            )

            schema_str = json.dumps(output_schema, indent=2, ensure_ascii=False)
            enhanced_prompt = (
                f'{prompt}\n\nRETORNE APENAS JSON seguindo: {schema_str}'
            )

            contents: list = [enhanced_prompt]
            for image_data in images:
                media_type = self._detect_media_type(image_data)
                contents.append({
                    'mime_type': media_type,
                    'data': image_data,
                })

            response = json_model.generate_content(
                contents,
                request_options={'timeout': self._timeout},
            )

            response_text = response.text if response and response.text else ''
            extracted_data = self._extract_json_from_text(response_text)

            input_tokens = 0
            output_tokens = 0
            if hasattr(response, 'usage_metadata') and response.usage_metadata:
                input_tokens = getattr(response.usage_metadata, 'prompt_token_count', 0)
                output_tokens = getattr(response.usage_metadata, 'candidates_token_count', 0)

            return AnalysisResult(
                text=response_text,
                extracted_data=extracted_data,
                tokens_used=input_tokens + output_tokens,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
        except Exception as e:
            logger.warning(
                'GoogleProvider: falha no response_mime_type, fallback — %s',
                str(e),
            )
            return super().analyze_images_structured(images, prompt, output_schema)

    @retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=30.0)
    def analyze_images(self, images: list[bytes], prompt: str) -> AnalysisResult:
        """Analisa multiplas imagens usando Gemini Vision."""
        logger.info(
            'GoogleProvider: analisando %d imagem(ns) com modelo %s',
            len(images),
            self._model,
        )

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

        # Calcula tokens usados (detalhado por input/output)
        input_tokens = 0
        output_tokens = 0
        if hasattr(response, 'usage_metadata') and response.usage_metadata:
            input_tokens = getattr(
                response.usage_metadata, 'prompt_token_count', 0,
            )
            output_tokens = getattr(
                response.usage_metadata, 'candidates_token_count', 0,
            )
        tokens_used = input_tokens + output_tokens

        # Tenta extrair JSON da resposta
        extracted_data = self._extract_json_from_text(response_text)

        logger.info(
            'GoogleProvider: analise concluida. Tokens usados: %d (in=%d, out=%d)',
            tokens_used, input_tokens, output_tokens,
        )

        return AnalysisResult(
            text=response_text,
            extracted_data=extracted_data,
            tokens_used=tokens_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
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

    def _estimate_image_tokens(self, images: list[bytes]) -> int:
        """Ollama: ~500 tokens por imagem (estimativa para modelos locais)."""
        return len(images) * 500

    def _get_context_limit(self) -> int:
        """Modelos locais geralmente tem contexto menor (8k-32k)."""
        return 32000

    def analyze_image(self, image_data: bytes, prompt: str) -> AnalysisResult:
        """Analisa uma unica imagem usando Ollama local."""
        return self.analyze_images([image_data], prompt)

    @retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=30.0)
    def analyze_images(self, images: list[bytes], prompt: str) -> AnalysisResult:
        """Analisa multiplas imagens usando Ollama local."""
        logger.info(
            'OllamaProvider: analisando %d imagem(ns) com modelo %s em %s',
            len(images),
            self._model,
            self._base_url,
        )

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
        input_tokens = data.get('prompt_eval_count', 0)
        output_tokens = data.get('eval_count', 0)
        tokens_used = input_tokens + output_tokens

        # Tenta extrair JSON da resposta
        extracted_data = self._extract_json_from_text(response_text)

        logger.info(
            'OllamaProvider: analise concluida. Tokens usados: %d (in=%d, out=%d)',
            tokens_used, input_tokens, output_tokens,
        )

        return AnalysisResult(
            text=response_text,
            extracted_data=extracted_data,
            tokens_used=tokens_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )

    def list_models(self) -> list[dict]:
        """
        Lista modelos disponiveis no servidor Ollama (13.3.2).

        Returns:
            Lista de dicts com informacoes de cada modelo.
        """
        try:
            with httpx.Client(timeout=10.0) as client:
                response = client.get(f'{self._base_url}/api/tags')
                response.raise_for_status()

            data = response.json()
            models = data.get('models', [])

            result = []
            for m in models:
                name = m.get('name', '')
                # Auto-deteccao de modelos com visao
                vision_keywords = ('llava', 'bakllava', 'moondream', 'vision', 'llama3.2')
                has_vision = any(kw in name.lower() for kw in vision_keywords)

                result.append({
                    'name': name,
                    'size': m.get('size', 0),
                    'modified_at': m.get('modified_at', ''),
                    'has_vision': has_vision,
                })

            logger.info(
                'OllamaProvider: %d modelos encontrados (%d com visao)',
                len(result),
                sum(1 for m in result if m['has_vision']),
            )
            return result

        except Exception as e:
            logger.error('OllamaProvider: erro ao listar modelos — %s', str(e))
            return []

    def analyze_images_streaming(
        self,
        images: list[bytes],
        prompt: str,
    ):
        """
        Analisa imagens com streaming de resposta (13.3.2).

        Yields:
            Chunks de texto da resposta conforme sao gerados.
        """
        b64_images = [self._encode_image_base64(img) for img in images]

        payload = {
            'model': self._model,
            'messages': [
                {
                    'role': 'user',
                    'content': prompt,
                    'images': b64_images,
                },
            ],
            'stream': True,
            'options': {
                'temperature': self._temperature,
                'num_predict': self._max_tokens,
            },
        }

        full_text = ''
        input_tokens = 0
        output_tokens = 0

        with httpx.Client(timeout=float(self._timeout)) as client:
            with client.stream(
                'POST',
                f'{self._base_url}/api/chat',
                json=payload,
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    try:
                        chunk = json.loads(line)
                        if 'message' in chunk and 'content' in chunk['message']:
                            text_chunk = chunk['message']['content']
                            full_text += text_chunk
                            yield text_chunk

                        # Ultima mensagem contem tokens
                        if chunk.get('done', False):
                            input_tokens = chunk.get('prompt_eval_count', 0)
                            output_tokens = chunk.get('eval_count', 0)
                    except json.JSONDecodeError:
                        continue


class OpenAICompatibleProvider(OpenAIProvider):
    """
    Provedor para APIs compativeis com OpenAI (13.3.1).

    Suporta Groq, Together, vLLM, e qualquer API que siga o formato
    da API da OpenAI (endpoint /v1/chat/completions).
    """

    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: int = 120,
        base_url: str = '',
    ) -> None:
        # Nao chama super().__init__() do OpenAIProvider para customizar base_url
        BaseLLMProvider.__init__(
            self, api_key, model, temperature,
            min(max_tokens, self._MAX_OUTPUT_TOKENS), timeout,
        )

        # Extrai base_url do api_key se nao fornecido explicitamente
        # Formato: "base_url|api_key" ou apenas api_key (com base_url separado)
        self._custom_base_url = base_url
        actual_api_key = api_key

        if '|' in api_key:
            parts = api_key.split('|', 1)
            self._custom_base_url = parts[0].strip()
            actual_api_key = parts[1].strip()

        if not self._custom_base_url:
            raise ValueError(
                'OpenAICompatibleProvider requer base_url. '
                'Forneça via parametro base_url ou no formato '
                '"base_url|api_key" no campo api_key.'
            )

        try:
            from openai import OpenAI
            self._client = OpenAI(
                api_key=actual_api_key,
                base_url=self._custom_base_url,
                timeout=float(self._timeout),
            )
        except ImportError:
            raise ImportError(
                'O pacote "openai" e necessario para usar o '
                'OpenAICompatibleProvider. Instale com: pip install openai'
            )

        logger.info(
            'OpenAICompatibleProvider: configurado com base_url=%s, modelo=%s',
            self._custom_base_url, self._model,
        )

    @property
    def provider_name(self) -> str:
        """Retorna 'openai-compatible' como nome do provider."""
        return 'openai-compatible'

    def analyze_images_structured(
        self,
        images: list[bytes],
        prompt: str,
        output_schema: dict | None = None,
    ) -> AnalysisResult:
        """Fallback para prompt-based structured output (nem todos suportam json_object)."""
        return BaseLLMProvider.analyze_images_structured(
            self, images, prompt, output_schema,
        )


class BedrockProvider(BaseLLMProvider):
    """
    Provedor LLM usando AWS Bedrock (13.3.3).

    Suporta Claude no Bedrock e outros modelos via boto3.
    Configuracao via AWS credentials no campo api_key:
    formato "access_key|secret_key|region" ou via env vars.
    """

    _MAX_OUTPUT_TOKENS = 64000

    def __init__(
        self,
        api_key: str,
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        timeout: int = 120,
    ) -> None:
        max_tokens = min(max_tokens, self._MAX_OUTPUT_TOKENS)
        super().__init__(api_key, model, temperature, max_tokens, timeout)

        # Parseia credenciais: "access_key|secret_key|region"
        self._region = 'us-east-1'
        aws_access_key = None
        aws_secret_key = None

        if api_key and '|' in api_key:
            parts = api_key.split('|')
            if len(parts) >= 3:
                aws_access_key = parts[0].strip()
                aws_secret_key = parts[1].strip()
                self._region = parts[2].strip()
            elif len(parts) == 2:
                aws_access_key = parts[0].strip()
                aws_secret_key = parts[1].strip()

        try:
            import boto3
            kwargs = {'region_name': self._region}
            if aws_access_key and aws_secret_key:
                kwargs['aws_access_key_id'] = aws_access_key
                kwargs['aws_secret_access_key'] = aws_secret_key

            self._bedrock = boto3.client(
                'bedrock-runtime', **kwargs,
            )
        except ImportError:
            raise ImportError(
                'O pacote "boto3" e necessario para usar o BedrockProvider. '
                'Instale com: pip install boto3'
            )

        logger.info(
            'BedrockProvider: configurado para regiao %s, modelo %s',
            self._region, self._model,
        )

    @property
    def provider_name(self) -> str:
        """Retorna 'bedrock' como nome do provider."""
        return 'bedrock'

    def _estimate_image_tokens(self, images: list[bytes]) -> int:
        """Bedrock Claude: mesma estimativa do Anthropic."""
        total = 0
        for img_bytes in images:
            w, h = self._get_image_dimensions(img_bytes)
            total += int(w * h / 750)
        return total

    def _get_context_limit(self) -> int:
        """Claude no Bedrock suporta 200k."""
        return 200000

    def analyze_image(self, image_data: bytes, prompt: str) -> AnalysisResult:
        """Analisa uma unica imagem usando Bedrock."""
        return self.analyze_images([image_data], prompt)

    @retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=30.0)
    def analyze_images(self, images: list[bytes], prompt: str) -> AnalysisResult:
        """Analisa multiplas imagens usando AWS Bedrock."""
        logger.info(
            'BedrockProvider: analisando %d imagem(ns) com modelo %s',
            len(images),
            self._model,
        )

        # Monta o payload no formato Anthropic Messages API (usado pelo Bedrock)
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

        body = json.dumps({
            'anthropic_version': 'bedrock-2023-05-31',
            'max_tokens': self._max_tokens,
            'temperature': self._temperature,
            'messages': [
                {'role': 'user', 'content': content},
            ],
        })

        response = self._bedrock.invoke_model(
            modelId=self._model,
            contentType='application/json',
            accept='application/json',
            body=body,
        )

        response_body = json.loads(response['body'].read())

        # Extrai texto
        response_text = ''
        for block in response_body.get('content', []):
            if block.get('type') == 'text':
                response_text += block.get('text', '')

        # Tokens
        usage = response_body.get('usage', {})
        input_tokens = usage.get('input_tokens', 0)
        output_tokens = usage.get('output_tokens', 0)
        tokens_used = input_tokens + output_tokens

        extracted_data = self._extract_json_from_text(response_text)

        logger.info(
            'BedrockProvider: analise concluida. Tokens usados: %d (in=%d, out=%d)',
            tokens_used, input_tokens, output_tokens,
        )

        return AnalysisResult(
            text=response_text,
            extracted_data=extracted_data,
            tokens_used=tokens_used,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
        )


# -------------------------------------------------------------------------
# Factory
# -------------------------------------------------------------------------

_PROVIDER_MAP: dict[str, type[BaseLLMProvider]] = {
    'anthropic': AnthropicProvider,
    'openai': OpenAIProvider,
    'openai-compatible': OpenAICompatibleProvider,
    'google': GoogleProvider,
    'ollama': OllamaProvider,
    'bedrock': BedrockProvider,
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
        provider_name: Nome do provedor ('anthropic', 'openai', 'openai-compatible',
                       'google', 'ollama', 'bedrock').
        api_key: Chave de API do provedor. Formatos especiais:
                 - Ollama: pode ser a URL base (http://host:11434)
                 - OpenAI-compatible: "base_url|api_key"
                 - Bedrock: "access_key|secret_key|region"
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
