import io
import logging
from typing import Any

from PIL import Image

logger = logging.getLogger(__name__)


class ImageOptimizer:
    """
    Otimizador de imagens para envio a provedores LLM.

    Redimensiona e comprime imagens de acordo com os limites
    de cada provider, reduzindo consumo de tokens de imagem
    sem perda significativa de qualidade visual.
    """

    # Limites de resolucao maxima (lado maior) por provider
    PROVIDER_MAX_DIMENSIONS: dict[str, int] = {
        'anthropic': 1568,   # 1568px no lado maior
        'openai': 2048,      # 2048px no modo high detail
        'google': 3072,      # Gemini suporta alta resolucao
        'ollama': 1024,      # Modelos locais geralmente menores
    }

    # Qualidade JPEG padrao
    DEFAULT_JPEG_QUALITY: int = 85

    # Tamanho limite (bytes) acima do qual forca conversao para JPEG
    _FORCE_JPEG_THRESHOLD: int = 500 * 1024  # 500KB

    @classmethod
    def optimize_for_provider(
        cls,
        image_bytes: bytes,
        provider: str,
        force_jpeg: bool = False,
    ) -> bytes:
        """
        Otimiza uma imagem para o provider LLM especificado.

        - Redimensiona se exceder limite do provider
        - Comprime para JPEG se force_jpeg=True ou imagem > 500KB
        - Mantem aspect ratio

        Args:
            image_bytes: Bytes originais da imagem.
            provider: Nome do provider LLM (anthropic, openai, google, ollama).
            force_jpeg: Se True, sempre converte para JPEG.

        Returns:
            Bytes da imagem otimizada.
        """
        try:
            img = Image.open(io.BytesIO(image_bytes))
        except Exception:
            logger.warning(
                'ImageOptimizer: imagem invalida (%d bytes), retornando original',
                len(image_bytes),
            )
            return image_bytes

        max_dim = cls.PROVIDER_MAX_DIMENSIONS.get(
            provider.lower(), 1568,
        )

        # Redimensiona se necessario
        img = cls._resize_image(img, max_dim)

        # Decide formato de saida
        should_jpeg = (
            force_jpeg
            or len(image_bytes) > cls._FORCE_JPEG_THRESHOLD
        )

        if should_jpeg:
            result = cls._to_jpeg(img, cls.DEFAULT_JPEG_QUALITY)
        else:
            # Mantem formato original se possivel
            original_format = getattr(img, 'format', None)
            if original_format and original_format.upper() == 'JPEG':
                result = cls._to_jpeg(img, cls.DEFAULT_JPEG_QUALITY)
            else:
                result = cls._to_png(img)

        return result

    @classmethod
    def optimize_batch(
        cls,
        images: list[bytes],
        provider: str,
    ) -> tuple[list[bytes], dict[str, Any]]:
        """
        Otimiza um batch de imagens. Retorna imagens otimizadas + stats.

        Args:
            images: Lista de imagens em bytes.
            provider: Nome do provider LLM.

        Returns:
            Tupla com (imagens otimizadas, stats dict).
            Stats: original_size, optimized_size, savings_percent, count.
        """
        original_size: int = sum(len(img) for img in images)
        optimized: list[bytes] = []

        for img_bytes in images:
            opt = cls.optimize_for_provider(img_bytes, provider)
            optimized.append(opt)

        optimized_size: int = sum(len(img) for img in optimized)
        savings_percent: float = (
            ((original_size - optimized_size) / original_size * 100.0)
            if original_size > 0
            else 0.0
        )

        stats: dict[str, Any] = {
            'original_size': original_size,
            'optimized_size': optimized_size,
            'savings_percent': round(savings_percent, 1),
            'count': len(images),
        }

        logger.info(
            'ImageOptimizer: batch de %d imagens otimizado — '
            'original=%d bytes, otimizado=%d bytes, economia=%.1f%%',
            len(images),
            original_size,
            optimized_size,
            savings_percent,
        )

        return optimized, stats

    @staticmethod
    def _resize_image(img: Image.Image, max_dimension: int) -> Image.Image:
        """
        Redimensiona mantendo aspect ratio.

        Apenas reduz; nunca amplia imagens menores que o limite.

        Args:
            img: Imagem PIL a ser redimensionada.
            max_dimension: Tamanho maximo permitido no lado maior.

        Returns:
            Imagem redimensionada (ou a mesma se ja estiver dentro do limite).
        """
        width, height = img.size

        if width <= max_dimension and height <= max_dimension:
            return img

        # Calcula novo tamanho mantendo proporcao
        if width >= height:
            new_width = max_dimension
            new_height = int(height * (max_dimension / width))
        else:
            new_height = max_dimension
            new_width = int(width * (max_dimension / height))

        resized = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

        logger.debug(
            'ImageOptimizer: redimensionado de %dx%d para %dx%d',
            width, height, new_width, new_height,
        )

        return resized

    @staticmethod
    def _to_jpeg(img: Image.Image, quality: int = 85) -> bytes:
        """
        Converte para JPEG com qualidade especificada.

        Converte imagens RGBA para RGB antes de salvar como JPEG.

        Args:
            img: Imagem PIL.
            quality: Qualidade JPEG (1-95).

        Returns:
            Bytes da imagem JPEG.
        """
        buf = io.BytesIO()

        # JPEG nao suporta canal alpha
        if img.mode in ('RGBA', 'LA', 'P'):
            img = img.convert('RGB')

        img.save(buf, format='JPEG', quality=quality, optimize=True)
        return buf.getvalue()

    @staticmethod
    def _to_png(img: Image.Image) -> bytes:
        """
        Converte para PNG.

        Args:
            img: Imagem PIL.

        Returns:
            Bytes da imagem PNG.
        """
        buf = io.BytesIO()
        img.save(buf, format='PNG', optimize=True)
        return buf.getvalue()
