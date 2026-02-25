import io
import logging
from dataclasses import dataclass

from PIL import Image

logger = logging.getLogger(__name__)


@dataclass
class ClassifiedScreenshot:
    """Screenshot classificado com score de relevancia."""

    image_bytes: bytes
    index: int
    relevance_score: float  # 0.0 a 1.0
    reason: str  # ex: 'page_loaded', 'after_login', 'data_content', 'final_state'
    phash: str  # perceptual hash


class ScreenshotClassifier:
    """Classificador de screenshots por relevancia e deduplicacao inteligente."""

    # Threshold de distancia Hamming para considerar screenshots duplicados
    HAMMING_THRESHOLD: int = 5

    @staticmethod
    def compute_phash(image_bytes: bytes) -> str:
        """
        Calcula perceptual hash (pHash) de uma imagem.

        Converte a imagem para escala de cinza, redimensiona para 8x8 pixels
        e gera um hash binario comparando cada pixel com a media.

        Args:
            image_bytes: Bytes da imagem (PNG, JPEG, etc).

        Returns:
            String binaria de 64 caracteres representando o pHash.
        """
        try:
            img = Image.open(io.BytesIO(image_bytes))
            # Converte para escala de cinza e redimensiona para 8x8
            img_gray = img.convert('L').resize((8, 8), Image.Resampling.LANCZOS)
            pixels = list(img_gray.getdata())
            # Calcula media dos pixels
            avg = sum(pixels) / len(pixels)
            # Gera hash: '1' se pixel > media, '0' caso contrario
            return ''.join('1' if px > avg else '0' for px in pixels)
        except Exception as e:
            logger.warning('Erro ao calcular pHash: %s', str(e))
            # Retorna hash vazio em caso de erro (nunca sera igual a outro hash valido)
            return '0' * 64

    @staticmethod
    def hamming_distance(hash1: str, hash2: str) -> int:
        """
        Calcula distancia de Hamming entre dois hashes.

        A distancia de Hamming e o numero de posicoes em que os bits diferem.
        Quanto menor a distancia, mais similares sao as imagens.

        Args:
            hash1: Primeiro hash binario.
            hash2: Segundo hash binario.

        Returns:
            Numero de bits diferentes entre os dois hashes.
        """
        if len(hash1) != len(hash2):
            return max(len(hash1), len(hash2))
        return sum(c1 != c2 for c1, c2 in zip(hash1, hash2))

    def deduplicate(self, screenshots: list[bytes]) -> list[ClassifiedScreenshot]:
        """
        Remove screenshots duplicados usando perceptual hashing.

        Compara cada screenshot com os ja aceitos usando distancia de Hamming.
        Se a distancia for menor que o threshold, o screenshot e considerado
        duplicado e descartado. Entre duplicados, mantem o de maior tamanho
        (melhor resolucao/qualidade).

        Args:
            screenshots: Lista de bytes de screenshots.

        Returns:
            Lista de ClassifiedScreenshot unicos, ordenados pela ordem original.
        """
        if not screenshots:
            return []

        # Calcula pHash para cada screenshot
        hashes: list[str] = []
        for img_bytes in screenshots:
            phash = self.compute_phash(img_bytes)
            hashes.append(phash)

        # Agrupa screenshots similares (clusters de duplicados)
        # Cada cluster e representado pelo screenshot de maior tamanho
        unique: list[ClassifiedScreenshot] = []
        unique_hashes: list[str] = []

        for i, (img_bytes, phash) in enumerate(zip(screenshots, hashes)):
            is_duplicate = False

            for j, existing_hash in enumerate(unique_hashes):
                distance = self.hamming_distance(phash, existing_hash)
                if distance <= self.HAMMING_THRESHOLD:
                    is_duplicate = True
                    # Se o novo screenshot e maior (melhor qualidade), substitui
                    if len(img_bytes) > len(unique[j].image_bytes):
                        unique[j] = ClassifiedScreenshot(
                            image_bytes=img_bytes,
                            index=i,
                            relevance_score=unique[j].relevance_score,
                            reason=unique[j].reason,
                            phash=phash,
                        )
                        unique_hashes[j] = phash
                    break

            if not is_duplicate:
                # Atribui razao basica pela posicao
                reason = self._reason_by_position(i, len(screenshots))
                score = self._base_score_by_position(i, len(screenshots))

                unique.append(ClassifiedScreenshot(
                    image_bytes=img_bytes,
                    index=i,
                    relevance_score=score,
                    reason=reason,
                    phash=phash,
                ))
                unique_hashes.append(phash)

        return unique

    def classify_and_select(
        self,
        screenshots: list[bytes],
        max_screenshots: int = 10,
        logs: list[str] | None = None,
    ) -> list[ClassifiedScreenshot]:
        """
        Classifica, deduplica e seleciona os screenshots mais relevantes.

        Criterios de relevancia:
        - Primeiro screenshot: relevance_score = 0.9 (page_loaded)
        - Ultimo screenshot: relevance_score = 0.95 (final_state)
        - Screenshots do meio com alta diferenca visual: 0.7-0.8
        - Screenshots similares ao anterior: 0.1-0.3

        Retorna ate max_screenshots screenshots ordenados por relevancia.

        Args:
            screenshots: Lista de bytes de screenshots.
            max_screenshots: Numero maximo de screenshots a retornar.
            logs: Lista opcional para registrar logs do processo.

        Returns:
            Lista de ClassifiedScreenshot selecionados, limitada a max_screenshots.
        """
        if not screenshots:
            return []

        if logs is None:
            logs = []

        # Passo 1: Calcula pHash para todos
        hashes: list[str] = []
        for img_bytes in screenshots:
            hashes.append(self.compute_phash(img_bytes))

        # Passo 2: Classifica cada screenshot
        classified: list[ClassifiedScreenshot] = []
        total = len(screenshots)

        for i, (img_bytes, phash) in enumerate(zip(screenshots, hashes)):
            # Calcula diferenca visual em relacao ao anterior
            visual_diff = 64  # Maximo (totalmente diferente) para o primeiro
            if i > 0:
                visual_diff = self.hamming_distance(phash, hashes[i - 1])

            # Determina relevancia baseada na posicao e diferenca visual
            score, reason = self._compute_relevance(
                index=i,
                total=total,
                visual_diff=visual_diff,
            )

            classified.append(ClassifiedScreenshot(
                image_bytes=img_bytes,
                index=i,
                relevance_score=score,
                reason=reason,
                phash=phash,
            ))

        # Passo 3: Deduplica (remove screenshots com distancia Hamming <= threshold)
        deduplicated = self._deduplicate_classified(classified)

        if len(deduplicated) < len(classified):
            logs.append(
                f'Screenshots deduplicados via pHash: {len(classified)} -> {len(deduplicated)}'
            )

        # Passo 4: Se ainda excede o limite, seleciona os mais relevantes
        if len(deduplicated) <= max_screenshots:
            return deduplicated

        # Garante que primeiro e ultimo sempre sao incluidos
        first = deduplicated[0] if deduplicated else None
        last = deduplicated[-1] if len(deduplicated) > 1 else None

        # Ordena os do meio por relevancia (descrescente)
        middle = deduplicated[1:-1] if len(deduplicated) > 2 else []
        middle_sorted = sorted(middle, key=lambda c: c.relevance_score, reverse=True)

        # Monta resultado: primeiro + melhores do meio + ultimo
        result: list[ClassifiedScreenshot] = []
        if first:
            result.append(first)

        # Calcula quantos do meio cabem
        slots_for_middle = max_screenshots - (1 if first else 0) - (1 if last else 0)
        result.extend(middle_sorted[:slots_for_middle])

        if last and last != first:
            result.append(last)

        # Reordena pela posicao original (index)
        result.sort(key=lambda c: c.index)

        logs.append(
            f'Screenshots selecionados por relevancia: {len(deduplicated)} -> {len(result)}'
        )

        return result

    def select_for_analysis(
        self,
        classified: list[ClassifiedScreenshot],
        max_analysis: int = 3,
    ) -> list[ClassifiedScreenshot]:
        """
        Seleciona os melhores screenshots para envio ao LLM.

        Prioriza screenshots com maior score de relevancia,
        garantindo diversidade visual (nao envia duplicados).

        Args:
            classified: Lista de screenshots ja classificados.
            max_analysis: Numero maximo de screenshots para analise LLM.

        Returns:
            Lista dos melhores screenshots para analise, limitada a max_analysis.
        """
        if not classified:
            return []

        if len(classified) <= max_analysis:
            return classified

        # Ordena por relevancia (decrescente)
        sorted_by_relevance = sorted(
            classified,
            key=lambda c: c.relevance_score,
            reverse=True,
        )

        # Seleciona os mais relevantes garantindo diversidade visual
        selected: list[ClassifiedScreenshot] = []
        selected_hashes: list[str] = []

        for candidate in sorted_by_relevance:
            if len(selected) >= max_analysis:
                break

            # Verifica se e visualmente diferente dos ja selecionados
            is_too_similar = False
            for existing_hash in selected_hashes:
                if self.hamming_distance(candidate.phash, existing_hash) <= self.HAMMING_THRESHOLD:
                    is_too_similar = True
                    break

            if not is_too_similar:
                selected.append(candidate)
                selected_hashes.append(candidate.phash)

        # Se nao conseguiu preencher todas as vagas, relaxa o criterio de similaridade
        if len(selected) < max_analysis:
            for candidate in sorted_by_relevance:
                if len(selected) >= max_analysis:
                    break
                if candidate not in selected:
                    selected.append(candidate)

        # Reordena pela posicao original
        selected.sort(key=lambda c: c.index)

        return selected

    def _compute_relevance(
        self,
        index: int,
        total: int,
        visual_diff: int,
    ) -> tuple[float, str]:
        """
        Calcula score de relevancia e razao para um screenshot.

        Args:
            index: Posicao do screenshot na sequencia (0-based).
            total: Numero total de screenshots.
            visual_diff: Distancia de Hamming em relacao ao screenshot anterior.

        Returns:
            Tupla (score, reason) com score entre 0.0 e 1.0.
        """
        # Primeiro screenshot: pagina carregada
        if index == 0:
            return 0.9, 'page_loaded'

        # Ultimo screenshot: estado final
        if index == total - 1:
            return 0.95, 'final_state'

        # Screenshots do meio: score baseado na diferenca visual
        if visual_diff > self.HAMMING_THRESHOLD:
            # Alta diferenca visual — conteudo novo/relevante
            # Normaliza a diferenca visual para um score entre 0.7 e 0.85
            # Maximo visual_diff possivel = 64 (completamente diferente)
            normalized_diff = min(visual_diff / 64.0, 1.0)
            score = 0.7 + (normalized_diff * 0.15)
            return score, 'data_content'
        else:
            # Baixa diferenca visual — screenshot similar ao anterior
            # Score proporcional a diferenca (mais diferente = maior score)
            normalized_diff = visual_diff / max(self.HAMMING_THRESHOLD, 1)
            score = 0.1 + (normalized_diff * 0.2)
            return score, 'similar_to_previous'

    def _deduplicate_classified(
        self,
        classified: list[ClassifiedScreenshot],
    ) -> list[ClassifiedScreenshot]:
        """
        Remove duplicados de uma lista ja classificada, mantendo o de maior tamanho.

        Args:
            classified: Lista de ClassifiedScreenshot a dedupliar.

        Returns:
            Lista sem duplicados, mantendo a ordem original.
        """
        if not classified:
            return []

        unique: list[ClassifiedScreenshot] = []
        unique_hashes: list[str] = []

        for item in classified:
            is_duplicate = False

            for j, existing_hash in enumerate(unique_hashes):
                distance = self.hamming_distance(item.phash, existing_hash)
                if distance <= self.HAMMING_THRESHOLD:
                    is_duplicate = True
                    # Mantem o de maior tamanho (bytes) entre duplicados
                    if len(item.image_bytes) > len(unique[j].image_bytes):
                        # Preserva o score mais alto entre os dois
                        best_score = max(item.relevance_score, unique[j].relevance_score)
                        best_reason = (
                            item.reason
                            if item.relevance_score >= unique[j].relevance_score
                            else unique[j].reason
                        )
                        unique[j] = ClassifiedScreenshot(
                            image_bytes=item.image_bytes,
                            index=item.index,
                            relevance_score=best_score,
                            reason=best_reason,
                            phash=item.phash,
                        )
                        unique_hashes[j] = item.phash
                    break

            if not is_duplicate:
                unique.append(item)
                unique_hashes.append(item.phash)

        return unique

    @staticmethod
    def _reason_by_position(index: int, total: int) -> str:
        """
        Atribui razao de relevancia baseada na posicao do screenshot.

        Args:
            index: Posicao do screenshot (0-based).
            total: Numero total de screenshots.

        Returns:
            String descrevendo o motivo da relevancia.
        """
        if index == 0:
            return 'page_loaded'
        if index == total - 1:
            return 'final_state'
        # Segundo screenshot frequentemente e apos login
        if index == 1 and total > 2:
            return 'after_login'
        return 'data_content'

    @staticmethod
    def _base_score_by_position(index: int, total: int) -> float:
        """
        Calcula score base de relevancia pela posicao.

        Args:
            index: Posicao do screenshot (0-based).
            total: Numero total de screenshots.

        Returns:
            Score de relevancia entre 0.0 e 1.0.
        """
        if index == 0:
            return 0.9
        if index == total - 1:
            return 0.95
        if index == 1 and total > 2:
            return 0.85
        # Screenshots intermediarios recebem score decrescente
        # Quanto mais proximo do meio, menor o score base
        return 0.75
