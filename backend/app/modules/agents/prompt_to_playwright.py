import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class PlaywrightAction:
    """Acao Playwright extraida do prompt."""

    action_type: str  # 'goto', 'click', 'fill', 'wait', 'screenshot'
    selector: str | None = None
    value: str | None = None
    url: str | None = None


class PromptToPlaywright:
    """
    Converte instrucoes textuais em sequencia de acoes Playwright.

    Usado como fallback quando browser-use falha — extrai acoes
    executaveis do prompt do usuario usando heuristicas de parsing.
    """

    # Padroes regex para extrair acoes do prompt
    _URL_PATTERN: re.Pattern[str] = re.compile(
        r'https?://[^\s<>"{}|\\^`\[\]]+'
    )
    _CLICK_PATTERN_PT: re.Pattern[str] = re.compile(
        r'clique?\s+(?:em|no|na|nos|nas)\s+["\']?(.+?)["\']?(?:\s*[.,;]|\s*$)',
        re.IGNORECASE,
    )
    _CLICK_PATTERN_EN: re.Pattern[str] = re.compile(
        r'click\s+(?:on|the)?\s*["\']?(.+?)["\']?(?:\s*[.,;]|\s*$)',
        re.IGNORECASE,
    )
    _FILL_PATTERN_PT: re.Pattern[str] = re.compile(
        r'preencha?\s+["\']?(.+?)["\']?\s+com\s+["\']?(.+?)["\']?(?:\s*[.,;]|\s*$)',
        re.IGNORECASE,
    )
    _FILL_PATTERN_EN: re.Pattern[str] = re.compile(
        r'(?:type|fill|enter)\s+["\']?(.+?)["\']?\s+(?:in|into)\s+["\']?(.+?)["\']?(?:\s*[.,;]|\s*$)',
        re.IGNORECASE,
    )
    _WAIT_PATTERN: re.Pattern[str] = re.compile(
        r'(?:aguarde|wait|espere)\s*(\d+)?\s*(?:s(?:egundos?)?|seconds?)?',
        re.IGNORECASE,
    )
    _SCREENSHOT_PATTERN: re.Pattern[str] = re.compile(
        r'(?:capture|screenshot|captura|print)',
        re.IGNORECASE,
    )

    @classmethod
    def parse(
        cls,
        prompt: str,
        base_url: str,
        additional_urls: list[str] | None = None,
    ) -> list[PlaywrightAction]:
        """
        Extrai acoes Playwright do prompt.

        Heuristicas:
        - URLs mencionadas -> goto actions
        - "clique em X" / "click X" -> click actions
        - "preencha X com Y" / "type Y in X" -> fill actions
        - "aguarde" / "wait" -> wait actions
        - "capture" / "screenshot" -> screenshot actions

        Args:
            prompt: Texto do prompt do usuario.
            base_url: URL base do projeto.
            additional_urls: URLs adicionais dos parametros de execucao.

        Returns:
            Lista de PlaywrightAction a serem executadas em ordem.
        """
        actions: list[PlaywrightAction] = []

        # Sempre comeca navegando para a URL base
        actions.append(PlaywrightAction(action_type='goto', url=base_url))

        # Extrai URLs mencionadas no corpo do prompt
        urls_in_prompt = cls._URL_PATTERN.findall(prompt)
        for url in urls_in_prompt:
            # Evita duplicar a URL base
            if url.rstrip('/') != base_url.rstrip('/'):
                actions.append(PlaywrightAction(action_type='goto', url=url))

        # URLs adicionais dos parametros de execucao
        for url in (additional_urls or []):
            full_url = (
                url if url.startswith('http')
                else f'{base_url.rstrip("/")}/{url.lstrip("/")}'
            )
            actions.append(PlaywrightAction(action_type='goto', url=full_url))

        # Tenta extrair acoes de preenchimento (fill) — verificar antes de click
        fill_matches_pt = cls._FILL_PATTERN_PT.findall(prompt)
        for field, value in fill_matches_pt:
            selector = cls._text_to_selector(field.strip())
            actions.append(PlaywrightAction(
                action_type='fill',
                selector=selector,
                value=value.strip(),
            ))

        fill_matches_en = cls._FILL_PATTERN_EN.findall(prompt)
        for value, field in fill_matches_en:
            selector = cls._text_to_selector(field.strip())
            actions.append(PlaywrightAction(
                action_type='fill',
                selector=selector,
                value=value.strip(),
            ))

        # Tenta extrair acoes de clique
        click_matches_pt = cls._CLICK_PATTERN_PT.findall(prompt)
        for target in click_matches_pt:
            selector = cls._text_to_selector(target.strip())
            actions.append(PlaywrightAction(
                action_type='click',
                selector=selector,
            ))

        click_matches_en = cls._CLICK_PATTERN_EN.findall(prompt)
        for target in click_matches_en:
            selector = cls._text_to_selector(target.strip())
            actions.append(PlaywrightAction(
                action_type='click',
                selector=selector,
            ))

        # Tenta extrair acoes de espera
        wait_matches = cls._WAIT_PATTERN.findall(prompt)
        for seconds_str in wait_matches:
            wait_ms = str(int(seconds_str) * 1000) if seconds_str else '2000'
            actions.append(PlaywrightAction(
                action_type='wait',
                value=wait_ms,
            ))

        # Screenshot no final (sempre)
        actions.append(PlaywrightAction(action_type='screenshot'))

        logger.debug(
            'PromptToPlaywright: extraidas %d acoes do prompt',
            len(actions),
        )

        return actions

    @classmethod
    async def execute(
        cls,
        page: 'object',
        actions: list[PlaywrightAction],
        logs: list[str],
        screenshots: list[bytes],
    ) -> None:
        """
        Executa a sequencia de acoes Playwright na pagina.

        Cada acao e executada com tratamento de erro individual —
        falhas em uma acao nao impedem a execucao das seguintes.

        Args:
            page: Instancia da pagina Playwright.
            actions: Lista de acoes a executar.
            logs: Lista de logs para registrar as acoes.
            screenshots: Lista de bytes onde screenshots serao adicionados.
        """
        for i, action in enumerate(actions):
            try:
                if action.action_type == 'goto' and action.url:
                    logs.append(f'Fallback: navegando para {action.url}')
                    await page.goto(
                        action.url,
                        wait_until='domcontentloaded',
                        timeout=30000,
                    )
                    await page.wait_for_timeout(2000)

                elif action.action_type == 'click' and action.selector:
                    logs.append(f'Fallback: clicando em {action.selector}')
                    await page.click(action.selector, timeout=10000)
                    await page.wait_for_timeout(1000)

                elif action.action_type == 'fill' and action.selector and action.value:
                    logs.append(f'Fallback: preenchendo {action.selector}')
                    await page.fill(action.selector, action.value, timeout=10000)

                elif action.action_type == 'screenshot':
                    try:
                        img = await page.screenshot(type='png')
                        screenshots.append(img)
                        logs.append(
                            f'Fallback: screenshot #{len(screenshots)} capturado'
                        )
                    except Exception:
                        logs.append('Fallback: erro ao capturar screenshot')

                elif action.action_type == 'wait':
                    wait_ms = int(action.value or '2000')
                    await page.wait_for_timeout(wait_ms)

            except Exception as e:
                logs.append(
                    f'Fallback: erro na acao {action.action_type}: '
                    f'{str(e)[:100]}'
                )

    @staticmethod
    def _text_to_selector(text: str) -> str:
        """
        Converte descricao textual de um elemento em seletor CSS/Playwright.

        Heuristicas:
        - Se parece com seletor CSS (#id, .class, tag[attr]), usa direto
        - Se e texto puro, tenta :has-text() ou placeholder match
        - Se contem 'botao'/'button', filtra por tag button

        Args:
            text: Descricao textual do elemento.

        Returns:
            Seletor CSS/Playwright para localizar o elemento.
        """
        # Se ja parece um seletor CSS, retorna direto
        if text.startswith(('#', '.', '[')) or '=' in text:
            return text

        # Se menciona 'botao' ou 'button', busca por botao com texto
        lower_text = text.lower()
        if 'botao' in lower_text or 'button' in lower_text or 'btn' in lower_text:
            # Remove a palavra 'botao'/'button' e usa o restante como texto
            clean = re.sub(
                r'\b(?:bot[aã]o|button|btn)\b',
                '',
                text,
                flags=re.IGNORECASE,
            ).strip()
            if clean:
                return f'button:has-text("{clean}")'
            return 'button[type="submit"]'

        # Se menciona 'link', busca por tag <a>
        if 'link' in lower_text:
            clean = re.sub(r'\blink\b', '', text, flags=re.IGNORECASE).strip()
            if clean:
                return f'a:has-text("{clean}")'
            return 'a'

        # Se menciona 'campo'/'field'/'input', busca por input
        if any(word in lower_text for word in ('campo', 'field', 'input')):
            clean = re.sub(
                r'\b(?:campo|field|input)\b',
                '',
                text,
                flags=re.IGNORECASE,
            ).strip()
            if clean:
                return f'input[placeholder*="{clean}"]'
            return 'input'

        # Caso generico: busca por texto visivel
        return f':has-text("{text}")'
