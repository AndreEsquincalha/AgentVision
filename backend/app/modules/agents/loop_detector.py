"""
Detector de loops para agentes de navegacao web.

Monitora URLs visitadas e acoes executadas para identificar
padroes de loop que indicam que o agente esta preso em um ciclo
repetitivo, desperdicando recursos e tempo.

Detecta quatro tipos de loop:
- url_repeat: mesma URL visitada N+ vezes
- url_cycle: sequencia ciclica de URLs (ex: A->B->C->A->B->C)
- stagnation: nenhuma URL nova visitada nos ultimos N steps
- action_repeat: mesma acao executada consecutivamente no mesmo alvo

Sprint 10.1.1 / 10.1.2
"""

import logging
from dataclasses import dataclass
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


@dataclass
class LoopDetection:
    """Resultado da deteccao de loop."""

    is_loop: bool
    loop_type: str  # 'url_repeat', 'url_cycle', 'stagnation', 'action_repeat'
    details: str
    count: int = 0


class LoopDetector:
    """
    Detector de loops para agentes de navegacao web.

    Monitora URLs visitadas e acoes executadas para identificar
    padroes de loop que indicam que o agente esta preso.
    """

    def __init__(
        self,
        max_url_repeats: int = 3,
        max_cycle_repeats: int = 2,
        stagnation_threshold: int = 5,
        max_action_repeats: int = 3,
    ) -> None:
        """
        Inicializa o detector de loops com thresholds configuraveis.

        Args:
            max_url_repeats: Numero maximo de visitas a mesma URL antes de considerar loop.
            max_cycle_repeats: Numero de repeticoes de um ciclo de URLs para considerar loop.
            stagnation_threshold: Numero de steps sem URL nova para considerar estagnacao.
            max_action_repeats: Numero de acoes consecutivas identicas para considerar loop.
        """
        self._max_url_repeats = max_url_repeats
        self._max_cycle_repeats = max_cycle_repeats
        self._stagnation_threshold = stagnation_threshold
        self._max_action_repeats = max_action_repeats
        self._url_history: list[tuple[str, datetime]] = []
        # (action_type, target, timestamp)
        self._action_history: list[tuple[str, str, datetime]] = []
        self._steps_since_new_url: int = 0
        self._last_unique_url_count: int = 0

    def record_url(self, url: str) -> LoopDetection | None:
        """
        Registra uma URL visitada e verifica se ha loop.

        Args:
            url: URL visitada pelo agente.

        Returns:
            LoopDetection se loop detectado, None caso contrario.
        """
        now = datetime.now(timezone.utc)
        self._url_history.append((url, now))

        # Verificar URL repetida
        url_count = sum(1 for u, _ in self._url_history if u == url)
        if url_count >= self._max_url_repeats:
            detection = LoopDetection(
                is_loop=True,
                loop_type='url_repeat',
                details=f'URL "{url}" visitada {url_count} vezes',
                count=url_count,
            )
            logger.warning('Loop detectado: %s', detection.details)
            return detection

        # Verificar progresso estagnado
        unique_urls = set(u for u, _ in self._url_history)
        if len(unique_urls) == self._last_unique_url_count:
            self._steps_since_new_url += 1
        else:
            self._steps_since_new_url = 0
            self._last_unique_url_count = len(unique_urls)

        if self._steps_since_new_url >= self._stagnation_threshold:
            detection = LoopDetection(
                is_loop=True,
                loop_type='stagnation',
                details=(
                    f'Nenhuma URL nova nos ultimos '
                    f'{self._steps_since_new_url} steps'
                ),
                count=self._steps_since_new_url,
            )
            logger.warning('Loop detectado: %s', detection.details)
            return detection

        # Verificar ciclo de URLs (A->B->C->A)
        cycle = self._detect_url_cycle()
        if cycle:
            logger.warning('Loop detectado: %s', cycle.details)
            return cycle

        return None

    def record_action(self, action_type: str, target: str) -> LoopDetection | None:
        """
        Registra uma acao executada e verifica se ha repeticao consecutiva.

        Args:
            action_type: Tipo da acao (click, type, navigate, etc).
            target: Alvo da acao (selector, URL, etc).

        Returns:
            LoopDetection se acao repetida detectada, None caso contrario.
        """
        now = datetime.now(timezone.utc)
        self._action_history.append((action_type, target, now))

        # Conta repeticoes consecutivas da mesma acao no mesmo alvo
        consecutive = 0
        for a_type, a_target, _ in reversed(self._action_history):
            if a_type == action_type and a_target == target:
                consecutive += 1
            else:
                break

        if consecutive >= self._max_action_repeats:
            detection = LoopDetection(
                is_loop=True,
                loop_type='action_repeat',
                details=(
                    f'Acao "{action_type}" no alvo "{target}" '
                    f'repetida {consecutive} vezes consecutivas'
                ),
                count=consecutive,
            )
            logger.warning('Loop detectado: %s', detection.details)
            return detection

        return None

    def check_all(self) -> LoopDetection | None:
        """
        Executa todas as verificacoes de loop no estado atual.

        Verifica estagnacao e ciclos de URLs sem registrar novas entradas.
        Util para verificacao periodica apos multiplos passos.

        Returns:
            LoopDetection se loop detectado, None caso contrario.
        """
        # Verificar estagnacao
        if self._steps_since_new_url >= self._stagnation_threshold:
            return LoopDetection(
                is_loop=True,
                loop_type='stagnation',
                details=(
                    f'Nenhuma URL nova nos ultimos '
                    f'{self._steps_since_new_url} steps'
                ),
                count=self._steps_since_new_url,
            )

        # Verificar ciclo de URLs
        cycle = self._detect_url_cycle()
        if cycle:
            return cycle

        # Verificar repeticao de acao consecutiva
        if len(self._action_history) >= self._max_action_repeats:
            last_action, last_target, _ = self._action_history[-1]
            consecutive = 0
            for a_type, a_target, _ in reversed(self._action_history):
                if a_type == last_action and a_target == last_target:
                    consecutive += 1
                else:
                    break

            if consecutive >= self._max_action_repeats:
                return LoopDetection(
                    is_loop=True,
                    loop_type='action_repeat',
                    details=(
                        f'Acao "{last_action}" no alvo "{last_target}" '
                        f'repetida {consecutive} vezes consecutivas'
                    ),
                    count=consecutive,
                )

        return None

    def _detect_url_cycle(self) -> LoopDetection | None:
        """
        Detecta ciclos na sequencia de URLs (ex: A->B->C->A->B->C).

        Verifica ciclos de tamanho 2 ate metade do historico.
        Um ciclo e confirmado quando a mesma sequencia se repete
        N vezes (configurado por max_cycle_repeats).

        Returns:
            LoopDetection se ciclo detectado, None caso contrario.
        """
        urls = [u for u, _ in self._url_history]
        if len(urls) < 4:
            return None

        # Verifica ciclos de tamanho 2 a len/2
        max_cycle_len = len(urls) // 2
        for cycle_len in range(2, max_cycle_len + 1):
            recent = urls[-cycle_len:]
            previous = urls[-(2 * cycle_len):-cycle_len]
            if recent == previous:
                # Conta quantas vezes o ciclo se repete
                repeat_count = 1
                for i in range(3, len(urls) // cycle_len + 1):
                    segment = urls[-(i * cycle_len):-(( i - 1) * cycle_len)]
                    if segment == recent:
                        repeat_count += 1
                    else:
                        break

                if repeat_count >= self._max_cycle_repeats:
                    cycle_str = ' -> '.join(recent)
                    return LoopDetection(
                        is_loop=True,
                        loop_type='url_cycle',
                        details=(
                            f'Ciclo detectado ({repeat_count}x): {cycle_str}'
                        ),
                        count=repeat_count,
                    )

        return None

    def reset(self) -> None:
        """Limpa todo o historico de URLs e acoes."""
        self._url_history.clear()
        self._action_history.clear()
        self._steps_since_new_url = 0
        self._last_unique_url_count = 0
        logger.debug('LoopDetector resetado')

    @property
    def stats(self) -> dict:
        """
        Retorna estatisticas do detector.

        Returns:
            Dicionario com total de URLs visitadas, URLs unicas,
            total de acoes e steps desde a ultima URL nova.
        """
        unique_urls = set(u for u, _ in self._url_history)
        return {
            'total_urls_visited': len(self._url_history),
            'unique_urls': len(unique_urls),
            'total_actions': len(self._action_history),
            'steps_since_new_url': self._steps_since_new_url,
        }
