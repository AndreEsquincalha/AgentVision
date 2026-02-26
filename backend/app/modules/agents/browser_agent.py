import asyncio
import base64
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Importacoes opcionais — outro agente cria esses modulos
# Se nao existirem ainda, as funcionalidades de loop detection e sandbox
# serao graciosamente desativadas
try:
    from app.modules.agents.loop_detector import LoopDetection, LoopDetector
    _HAS_LOOP_DETECTOR = True
except ImportError:
    _HAS_LOOP_DETECTOR = False
    LoopDetector = None  # type: ignore[assignment, misc]
    LoopDetection = None  # type: ignore[assignment, misc]

try:
    from app.modules.agents.agent_sandbox import AgentSandbox, SandboxViolation
    _HAS_AGENT_SANDBOX = True
except ImportError:
    _HAS_AGENT_SANDBOX = False
    AgentSandbox = None  # type: ignore[assignment, misc]
    SandboxViolation = None  # type: ignore[assignment, misc]

# Timeouts granulares por fase (em milissegundos)
_LOGIN_TIMEOUT_MS: int = 30_000       # 30s para login
_NAVIGATION_TIMEOUT_MS: int = 60_000  # 60s por navegacao
_EXTRACTION_TIMEOUT_MS: int = 30_000  # 30s para extracao
_PAGE_READY_TIMEOUT_MS: int = 5_000   # 5s para estabilizacao da pagina

# Seletores comuns de modais/popups para fechamento automatico
_MODAL_CLOSE_SELECTORS: list[str] = [
    'button[aria-label="Close"]',
    'button[aria-label="Fechar"]',
    '.modal-close',
    '[data-dismiss="modal"]',
    'button:has-text("Accept")',
    'button:has-text("Aceitar")',
    'button:has-text("OK")',
    '#cookie-accept',
    '.cookie-close',
]

# Seletores comuns para campos de login
_USERNAME_SELECTORS: list[str] = [
    'input[type="email"]',
    'input[name="email"]',
    'input[name="username"]',
    'input[name="login"]',
    'input[name="user"]',
    'input[id="email"]',
    'input[id="username"]',
    'input[id="login"]',
    'input[type="text"][name*="user"]',
    'input[type="text"][name*="email"]',
    'input[type="text"][name*="login"]',
    '#email',
    '#username',
    '#login',
]

_PASSWORD_SELECTORS: list[str] = [
    'input[type="password"]',
    'input[name="password"]',
    'input[name="passwd"]',
    'input[name="pass"]',
    'input[id="password"]',
    '#password',
]

_SUBMIT_SELECTORS: list[str] = [
    'button[type="submit"]',
    'input[type="submit"]',
    'button:has-text("Login")',
    'button:has-text("Entrar")',
    'button:has-text("Sign in")',
    'button:has-text("Log in")',
    'button:has-text("Submit")',
]


@dataclass
class BrowserResult:
    """Resultado da execucao do agente de navegacao."""

    screenshots: list[bytes] = field(default_factory=list)
    logs: list[str] = field(default_factory=list)
    extracted_content: list[str] = field(default_factory=list)
    success: bool = False
    error_message: str | None = None


class BrowserAgent:
    """
    Agente de navegacao web com captura de screenshots.

    Utiliza a biblioteca browser-use com Playwright para navegar em sites,
    executar acoes guiadas por prompt e capturar screenshots nos momentos relevantes.
    Quando browser-use nao esta disponivel ou nao pode ser usado (ex: sem LLM),
    faz fallback para Playwright dirigido com PromptToPlaywright.

    Melhorias Sprint 10:
    - Circuit breaker com LoopDetector (10.1.3)
    - max_steps dinamico (10.1.4)
    - Sandbox de seguranca via prompt (10.2.2)
    - Timeouts granulares por fase (10.2.3)
    - Prompt assertivo reestruturado (10.3.1)
    - Fallback inteligente com PromptToPlaywright (10.3.2)
    - Deteccao de estado da pagina (10.3.3)
    - Retry inteligente com diagnostico de erro (10.3.4)
    """

    def __init__(
        self,
        base_url: str,
        credentials: dict | None = None,
        headless: bool = True,
        timeout: int = 120,
        timeout_per_step: int = 60,
        max_steps: int | None = None,
    ) -> None:
        """
        Inicializa o agente de navegacao.

        Args:
            base_url: URL base do site a ser navegado.
            credentials: Dicionario com credenciais de login (ex: {username: '...', password: '...'}).
            headless: Se True, executa o navegador em modo headless (sem interface grafica).
            timeout: Timeout base em segundos (usado no fallback Playwright).
            timeout_per_step: Timeout maximo por step do agente (segundos).
            max_steps: Numero maximo de steps para o agente. Se None, sera
                       determinado por execution_params ou default (20).
        """
        self._base_url = base_url
        self._credentials = credentials
        self._headless = headless
        self._timeout = timeout
        self._timeout_per_step = timeout_per_step
        self._max_steps = max_steps

    async def run(
        self,
        prompt: str,
        execution_params: dict | None = None,
    ) -> BrowserResult:
        """
        Executa a navegacao guiada pelo prompt.

        Tenta usar browser-use + LLM agent. Se nao for possivel
        (sem LLM configurado ou falha), faz fallback para Playwright dirigido
        usando PromptToPlaywright para extrair acoes do prompt.

        Args:
            prompt: Instrucoes de navegacao para o agente.
            execution_params: Parametros adicionais de execucao (URLs especificas,
                              dados a procurar, tempos de espera, configuracao de LLM, etc).

        Returns:
            Resultado contendo screenshots capturados, logs e status.
        """
        execution_params = execution_params or {}

        # Verifica se ha configuracao de LLM nos parametros de execucao
        # para usar o agente inteligente do browser-use
        llm_config = execution_params.get('llm_config')

        if llm_config:
            try:
                return await self._run_with_browser_use(
                    prompt=prompt,
                    execution_params=execution_params,
                    llm_config=llm_config,
                )
            except Exception as e:
                logger.warning(
                    'Falha ao executar com browser-use, tentando fallback Playwright: %s',
                    str(e),
                )
                # Fallback para Playwright dirigido com PromptToPlaywright
                return await self._run_with_playwright(
                    prompt=prompt,
                    execution_params=execution_params,
                )
        else:
            # Sem LLM, usa Playwright dirigido
            return await self._run_with_playwright(
                prompt=prompt,
                execution_params=execution_params,
            )

    # ------------------------------------------------------------------ #
    #  Modo browser-use (com LLM)
    # ------------------------------------------------------------------ #

    async def _run_with_browser_use(
        self,
        prompt: str,
        execution_params: dict,
        llm_config: dict,
    ) -> BrowserResult:
        """
        Executa navegacao usando browser-use com agente de IA.

        Integra circuit breaker (LoopDetector), sandbox rules no prompt,
        e max_steps dinamico.

        Args:
            prompt: Instrucoes de navegacao.
            execution_params: Parametros adicionais.
            llm_config: Configuracao do LLM (provider, model, api_key).

        Returns:
            Resultado da navegacao.
        """
        from browser_use import Agent, Browser

        logs: list[str] = []
        screenshots: list[bytes] = []
        browser = None

        try:
            logs.append(f'Iniciando browser-use agent para {self._base_url}')

            # Configura o navegador
            browser = Browser(
                headless=self._headless,
            )

            # Configura o LLM para o agente
            llm = self._create_langchain_llm(llm_config)

            # Monta o prompt completo com contexto, sandbox e instrucoes assertivas
            full_prompt = self._build_full_prompt(prompt, execution_params)

            logs.append(f'Navegando para {self._base_url}')
            logs.append(
                f'Prompt: {prompt[:200]}...' if len(prompt) > 200
                else f'Prompt: {prompt}'
            )

            # max_steps dinamico (10.1.4):
            # Prioridade: execution_params > construtor > default
            max_steps = self._resolve_max_steps(execution_params)

            # Cria e executa o agente
            agent = Agent(
                task=full_prompt,
                llm=llm,
                browser=browser,
                use_vision=True,
                max_steps=max_steps,
            )

            # Timeout inteligente: max_steps * timeout_per_step
            smart_timeout = float(max_steps * self._timeout_per_step)
            logs.append(
                f'Timeout: {smart_timeout:.0f}s '
                f'({max_steps} steps x {self._timeout_per_step}s/step)'
            )

            history = await asyncio.wait_for(
                agent.run(),
                timeout=smart_timeout,
            )

            # Extrai screenshots do historico
            b64_screenshots = history.screenshots()
            if b64_screenshots:
                for i, b64_str in enumerate(b64_screenshots):
                    if b64_str:
                        try:
                            img_bytes = base64.b64decode(b64_str)
                            screenshots.append(img_bytes)
                            logs.append(
                                f'Capturando screenshot #{len(screenshots)}'
                            )
                        except Exception as decode_err:
                            logs.append(
                                f'Erro ao decodificar screenshot #{i}: '
                                f'{str(decode_err)}'
                            )

            # --- Circuit Breaker: analisa URLs visitadas (10.1.3) ---
            visited_urls = history.urls()
            loop_warning_injected = False
            if visited_urls:
                for url in visited_urls:
                    logs.append(f'URL visitada: {url}')

                # Verifica loops nas URLs usando LoopDetector
                if _HAS_LOOP_DETECTOR:
                    loop_detector = LoopDetector(
                        max_url_repeats=3,
                        max_cycle_repeats=2,
                        stagnation_threshold=5,
                        max_action_repeats=3,
                    )
                    loop_count = 0
                    for url in visited_urls:
                        detection = loop_detector.record_url(url)
                        if detection is not None:
                            loop_count += 1
                            if loop_count == 1:
                                # Primeira deteccao: warning, continua
                                logs.append(
                                    f'AVISO: Loop detectado ({detection}). '
                                    f'O agente pode estar repetindo acoes.'
                                )
                                loop_warning_injected = True
                            elif loop_count >= 2:
                                # Segunda deteccao: forca parada
                                logs.append(
                                    f'CRITICO: Loop persistente detectado '
                                    f'({detection}). Forcando parada do agente.'
                                )
                                # Captura screenshot final antes de parar
                                try:
                                    session = (
                                        browser._browser_session
                                        if hasattr(browser, '_browser_session')
                                        else None
                                    )
                                    if session:
                                        final_ss = await session.get_screenshot()
                                        if final_ss:
                                            screenshots.append(
                                                base64.b64decode(final_ss)
                                                if isinstance(final_ss, str)
                                                else final_ss
                                            )
                                            logs.append(
                                                'Screenshot final capturado antes da parada por loop'
                                            )
                                except Exception:
                                    logs.append(
                                        'Nao foi possivel capturar screenshot final apos loop'
                                    )

                                return BrowserResult(
                                    screenshots=screenshots,
                                    logs=logs,
                                    success=False,
                                    error_message=(
                                        'Loop detectado e agente forcado a parar'
                                    ),
                                )

            # Extrai conteudo extraido via acao "extract" durante a navegacao
            extracted_content: list[str] = []
            extracted = history.extracted_content()
            if extracted:
                for content in extracted:
                    if content:
                        content_str = str(content).strip()
                        if content_str:
                            extracted_content.append(content_str)
                            logs.append(
                                f'Conteudo extraido: {content_str[:200]}'
                            )

            # Resultado final do agente
            final = history.final_result()
            if final:
                final_str = str(final).strip()
                if final_str:
                    extracted_content.append(final_str)
                    logs.append(f'Resultado final: {final_str[:200]}')

            # Deduplica screenshots usando perceptual hashing (pHash)
            if len(screenshots) > 1:
                from app.modules.agents.screenshot_classifier import (
                    ScreenshotClassifier,
                )

                classifier = ScreenshotClassifier()
                classified = classifier.deduplicate(screenshots)
                original_count = len(screenshots)
                screenshots = [c.image_bytes for c in classified]
                if len(screenshots) < original_count:
                    logs.append(
                        f'Screenshots deduplicados via pHash: '
                        f'{original_count} -> {len(screenshots)}'
                    )

            # Limita numero maximo de screenshots usando classificacao por relevancia
            max_screenshots = execution_params.get('max_screenshots', 10)
            if len(screenshots) > max_screenshots:
                from app.modules.agents.screenshot_classifier import (
                    ScreenshotClassifier,
                )

                classifier = ScreenshotClassifier()
                original_count = len(screenshots)
                classified = classifier.classify_and_select(
                    screenshots,
                    max_screenshots=max_screenshots,
                    logs=logs,
                )
                screenshots = [c.image_bytes for c in classified]
                logs.append(
                    f'Screenshots limitados por relevancia: '
                    f'selecionados {len(screenshots)} de {original_count}'
                )

            # Extrai erros
            errors = history.errors()
            has_errors = False
            if errors:
                for error in errors:
                    if error:
                        has_errors = True
                        logs.append(
                            f'Erro durante navegacao: {str(error)[:200]}'
                        )

            is_done = history.is_done()

            # Se houve warning de loop mas o agente terminou, menciona nos logs
            if loop_warning_injected and is_done:
                logs.append(
                    'Agente concluiu apos aviso de loop '
                    '(possivelmente auto-corrigiu)'
                )

            logs.append(
                f'Navegacao concluida. Steps: {history.number_of_steps()}, '
                f'Screenshots: {len(screenshots)}, Sucesso: {is_done}'
            )

            return BrowserResult(
                screenshots=screenshots,
                logs=logs,
                extracted_content=extracted_content,
                success=is_done and not has_errors,
                error_message=(
                    None if not has_errors
                    else 'Erros encontrados durante navegacao'
                ),
            )

        except asyncio.TimeoutError:
            max_steps = self._resolve_max_steps(execution_params)
            smart_timeout = max_steps * self._timeout_per_step
            logs.append(
                f'Timeout atingido ({smart_timeout}s). '
                f'Capturando screenshot final.'
            )
            # Tenta capturar screenshot final em caso de timeout
            try:
                if browser:
                    session = (
                        browser._browser_session
                        if hasattr(browser, '_browser_session')
                        else None
                    )
                    if session:
                        final_screenshot = await session.get_screenshot()
                        if final_screenshot:
                            screenshots.append(
                                base64.b64decode(final_screenshot)
                                if isinstance(final_screenshot, str)
                                else final_screenshot
                            )
            except Exception:
                logs.append(
                    'Nao foi possivel capturar screenshot final apos timeout'
                )

            return BrowserResult(
                screenshots=screenshots,
                logs=logs,
                success=False,
                error_message=f'Timeout atingido ({smart_timeout}s)',
            )

        except Exception as e:
            error_msg = f'Erro no browser-use agent: {str(e)}'
            logs.append(f'Erro: {error_msg}')
            logger.error('BrowserAgent (browser-use): %s', error_msg)

            return BrowserResult(
                screenshots=screenshots,
                logs=logs,
                success=False,
                error_message=error_msg,
            )

        finally:
            # Limpeza do navegador
            if browser:
                try:
                    await browser.stop()
                    logs.append('Navegador fechado com sucesso')
                except Exception as close_err:
                    logger.warning(
                        'Erro ao fechar navegador: %s', str(close_err)
                    )

    # ------------------------------------------------------------------ #
    #  Modo Playwright dirigido (fallback)
    # ------------------------------------------------------------------ #

    async def _run_with_playwright(
        self,
        prompt: str,
        execution_params: dict,
    ) -> BrowserResult:
        """
        Executa navegacao usando Playwright dirigido (fallback inteligente).

        Em vez de navegacao generica, usa PromptToPlaywright para extrair
        acoes executaveis do prompt. Inclui deteccao de estado da pagina,
        retry inteligente, timeouts granulares e circuit breaker.

        Args:
            prompt: Instrucoes de navegacao (usadas para extrair acoes).
            execution_params: Parametros adicionais (URLs a visitar, wait_time, etc).

        Returns:
            Resultado da navegacao.
        """
        from app.modules.agents.prompt_to_playwright import PromptToPlaywright

        logs: list[str] = []
        screenshots: list[bytes] = []
        pooled_browser = None
        context = None

        # Inicializa LoopDetector se disponivel
        loop_detector: 'LoopDetector | None' = None
        if _HAS_LOOP_DETECTOR:
            loop_detector = LoopDetector(
                max_url_repeats=3,
                max_cycle_repeats=2,
                stagnation_threshold=5,
                max_action_repeats=3,
            )

        try:
            logs.append(
                f'Iniciando Playwright (fallback inteligente) para '
                f'{self._base_url}'
            )
            logs.append(
                f'Prompt: {prompt[:200]}...' if len(prompt) > 200
                else f'Prompt: {prompt}'
            )

            # Usa o pool de browsers para reutilizacao de instancias
            from app.modules.agents.browser_pool import get_browser_pool
            pool = await get_browser_pool(headless=self._headless)
            context, page, pooled_browser = await pool.acquire(
                timeout_ms=self._timeout * 1000,
            )
            logs.append('Browser adquirido do pool (reutilizacao)')

            # --- Fase 1: Navegacao inicial (com timeout granular) ---
            logs.append(f'Navegando para {self._base_url}')
            try:
                await page.goto(
                    self._base_url,
                    wait_until='domcontentloaded',
                    timeout=_NAVIGATION_TIMEOUT_MS,
                )
                await self._wait_for_page_ready(page)
                logs.append(f'Pagina carregada: {page.url}')
            except Exception as nav_err:
                logs.append(f'Erro na navegacao inicial: {str(nav_err)}')
                # Captura screenshot mesmo em caso de erro
                screenshot = await self._safe_screenshot(page)
                if screenshot:
                    screenshots.append(screenshot)
                    logs.append(
                        f'Capturando screenshot #{len(screenshots)} (erro)'
                    )
                return BrowserResult(
                    screenshots=screenshots,
                    logs=logs,
                    success=False,
                    error_message=(
                        f'Falha na navegacao para {self._base_url}: '
                        f'{str(nav_err)}'
                    ),
                )

            # Registra URL no loop detector
            if loop_detector:
                loop_detector.record_url(page.url)

            # Captura screenshot da pagina inicial
            screenshot = await self._safe_screenshot(page)
            if screenshot:
                screenshots.append(screenshot)
                logs.append(
                    f'Capturando screenshot #{len(screenshots)} '
                    f'(pagina inicial)'
                )

            # Espera opcional antes de continuar
            wait_time = execution_params.get('wait_time', 2)
            await page.wait_for_timeout(int(wait_time * 1000))

            # --- Fase 2: Login (com timeout granular de 30s) ---
            if self._credentials:
                login_success = await self._attempt_login(page, logs)
                if login_success:
                    # Captura screenshot apos login
                    await page.wait_for_timeout(2000)
                    screenshot = await self._safe_screenshot(page)
                    if screenshot:
                        screenshots.append(screenshot)
                        logs.append(
                            f'Capturando screenshot #{len(screenshots)} '
                            f'(apos login)'
                        )

            # --- Fase 3: Execucao de acoes via PromptToPlaywright ---
            additional_urls = execution_params.get('urls', [])
            actions = PromptToPlaywright.parse(
                prompt=prompt,
                base_url=self._base_url,
                additional_urls=additional_urls,
            )

            # Filtra a primeira acao goto (ja navegamos para base_url)
            filtered_actions = [
                a for a in actions
                if not (
                    a.action_type == 'goto'
                    and a.url
                    and a.url.rstrip('/') == self._base_url.rstrip('/')
                )
            ]

            logs.append(
                f'PromptToPlaywright: {len(filtered_actions)} acoes extraidas'
            )

            for action in filtered_actions:
                # Circuit breaker: verifica loop antes de cada navegacao
                if action.action_type == 'goto' and action.url:
                    if loop_detector:
                        detection = loop_detector.record_url(action.url)
                        if detection is not None:
                            logs.append(
                                f'Loop detectado para URL {action.url}: '
                                f'{detection}. Parando navegacao.'
                            )
                            break

                # Deteccao de estado da pagina antes de acoes interativas
                if action.action_type in ('click', 'fill'):
                    await self._wait_for_page_ready(page)

                # Executa acao individual com retry inteligente
                try:
                    if action.action_type == 'goto' and action.url:
                        logs.append(f'Navegando para {action.url}')

                        async def _nav_action(
                            url: str = action.url,
                        ) -> None:
                            await page.goto(
                                url,
                                wait_until='domcontentloaded',
                                timeout=_NAVIGATION_TIMEOUT_MS,
                            )

                        success = await self._smart_retry(
                            page, _nav_action, max_retries=2, logs=logs,
                        )
                        if success:
                            await self._wait_for_page_ready(page)
                            logs.append(f'Pagina carregada: {page.url}')
                            await page.wait_for_timeout(
                                int(wait_time * 1000)
                            )
                            # Captura screenshot
                            screenshot = await self._safe_screenshot(page)
                            if screenshot:
                                screenshots.append(screenshot)
                                logs.append(
                                    f'Capturando screenshot '
                                    f'#{len(screenshots)}'
                                )

                    elif action.action_type == 'click' and action.selector:
                        logs.append(f'Clicando em {action.selector}')

                        async def _click_action(
                            sel: str = action.selector,
                        ) -> None:
                            await page.click(
                                sel, timeout=_EXTRACTION_TIMEOUT_MS,
                            )

                        await self._smart_retry(
                            page, _click_action, max_retries=2, logs=logs,
                        )
                        await page.wait_for_timeout(1000)

                    elif (
                        action.action_type == 'fill'
                        and action.selector
                        and action.value
                    ):
                        logs.append(f'Preenchendo {action.selector}')

                        async def _fill_action(
                            sel: str = action.selector,
                            val: str = action.value,
                        ) -> None:
                            await page.fill(
                                sel, val, timeout=_EXTRACTION_TIMEOUT_MS,
                            )

                        await self._smart_retry(
                            page, _fill_action, max_retries=2, logs=logs,
                        )

                    elif action.action_type == 'screenshot':
                        screenshot = await self._safe_screenshot(page)
                        if screenshot:
                            screenshots.append(screenshot)
                            logs.append(
                                f'Capturando screenshot '
                                f'#{len(screenshots)}'
                            )

                    elif action.action_type == 'wait':
                        wait_ms = int(action.value or '2000')
                        await page.wait_for_timeout(wait_ms)

                except Exception as action_err:
                    logs.append(
                        f'Erro na acao {action.action_type}: '
                        f'{str(action_err)[:100]}'
                    )

            # --- Fase 4: Captura final ---
            # Captura screenshot final (full page)
            try:
                final_screenshot = await page.screenshot(
                    full_page=True,
                    type='png',
                )
                screenshots.append(final_screenshot)
                logs.append(
                    f'Capturando screenshot #{len(screenshots)} '
                    f'(pagina completa final)'
                )
            except Exception:
                logs.append(
                    'Nao foi possivel capturar screenshot final (full page)'
                )

            # Garante pelo menos um screenshot
            if not screenshots:
                screenshot = await self._safe_screenshot(page)
                if screenshot:
                    screenshots.append(screenshot)
                    logs.append(
                        f'Capturando screenshot #{len(screenshots)} '
                        f'(fallback)'
                    )

            logs.append(
                f'Navegacao concluida. Screenshots capturados: '
                f'{len(screenshots)}'
            )

            return BrowserResult(
                screenshots=screenshots,
                logs=logs,
                success=True,
                error_message=None,
            )

        except asyncio.TimeoutError:
            error_msg = f'Timeout atingido ({self._timeout}s)'
            logs.append(error_msg)
            return BrowserResult(
                screenshots=screenshots,
                logs=logs,
                success=False,
                error_message=error_msg,
            )

        except Exception as e:
            error_msg = f'Erro no Playwright: {str(e)}'
            logs.append(f'Erro: {error_msg}')
            logger.error('BrowserAgent (Playwright): %s', error_msg)
            return BrowserResult(
                screenshots=screenshots,
                logs=logs,
                success=False,
                error_message=error_msg,
            )

        finally:
            # Libera browser de volta ao pool (fecha apenas o context)
            if pooled_browser and context:
                try:
                    from app.modules.agents.browser_pool import get_browser_pool
                    pool = await get_browser_pool(headless=self._headless)
                    await pool.release(pooled_browser, context)
                    logs.append('Browser liberado de volta ao pool')
                except Exception as release_err:
                    logger.warning(
                        'Erro ao liberar browser para pool: %s', str(release_err)
                    )

    # ------------------------------------------------------------------ #
    #  Deteccao de estado da pagina (10.3.3)
    # ------------------------------------------------------------------ #

    @staticmethod
    async def _wait_for_page_ready(
        page: 'object',
        timeout_ms: int = _PAGE_READY_TIMEOUT_MS,
    ) -> None:
        """
        Aguarda pagina estabilizar antes de interagir.

        Verifica se o DOM foi carregado e tenta fechar modais/popups
        comuns que possam estar bloqueando a interacao.

        Args:
            page: Instancia da pagina Playwright.
            timeout_ms: Timeout maximo em milissegundos para aguardar estabilizacao.
        """
        try:
            await page.wait_for_load_state(
                'domcontentloaded', timeout=timeout_ms,
            )
        except Exception:
            pass

        # Tenta fechar modais/popups comuns
        for selector in _MODAL_CLOSE_SELECTORS:
            try:
                element = page.locator(selector).first
                if await element.is_visible(timeout=500):
                    await element.click()
                    break
            except Exception:
                continue

    # ------------------------------------------------------------------ #
    #  Retry inteligente (10.3.4)
    # ------------------------------------------------------------------ #

    @staticmethod
    async def _smart_retry(
        page: 'object',
        action_fn: 'object',
        max_retries: int = 2,
        logs: list[str] | None = None,
    ) -> bool:
        """
        Retry inteligente com analise de erro e ajuste de estrategia.

        Diagnostica o tipo de falha e aplica estrategia apropriada:
        - element not found -> aguardar 2s + retry
        - timeout -> aguardar 3s + retry
        - click intercepted -> scroll/fechar modal + retry

        Args:
            page: Instancia da pagina Playwright.
            action_fn: Funcao async que executa a acao.
            max_retries: Numero maximo de retentativas.
            logs: Lista opcional para registrar logs.

        Returns:
            True se a acao foi executada com sucesso, False caso contrario.
        """
        for attempt in range(max_retries + 1):
            try:
                await action_fn()
                return True
            except Exception as e:
                error_str = str(e).lower()
                if attempt >= max_retries:
                    if logs:
                        logs.append(
                            f'Acao falhou apos {max_retries + 1} '
                            f'tentativas: {str(e)[:100]}'
                        )
                    return False

                # Diagnostico e ajuste de estrategia por tipo de erro
                if 'not found' in error_str or 'no element' in error_str:
                    # Elemento nao encontrado: aguarda renderizacao
                    await page.wait_for_timeout(2000)
                elif 'timeout' in error_str:
                    # Timeout: espera mais antes de tentar novamente
                    await page.wait_for_timeout(3000)
                elif 'intercept' in error_str:
                    # Click interceptado por overlay: tenta fechar modal
                    await BrowserAgent._wait_for_page_ready(page)
                else:
                    # Erro generico: pequena pausa antes de retry
                    await page.wait_for_timeout(1000)

                if logs:
                    logs.append(
                        f'Retry {attempt + 1}/{max_retries}: '
                        f'{str(e)[:80]}'
                    )
        return False

    # ------------------------------------------------------------------ #
    #  Login automatico (com timeout granular e retry inteligente)
    # ------------------------------------------------------------------ #

    async def _attempt_login(
        self,
        page: 'object',
        logs: list[str],
    ) -> bool:
        """
        Tenta realizar login na pagina usando as credenciais configuradas.

        Procura por campos comuns de login (email, username, password)
        e tenta preencher e submeter o formulario. Usa timeout granular
        de 30s para toda a operacao de login.

        Args:
            page: Instancia da pagina Playwright.
            logs: Lista de logs para registrar as acoes.

        Returns:
            True se o login foi tentado, False caso contrario.
        """
        if not self._credentials:
            return False

        username = (
            self._credentials.get('username')
            or self._credentials.get('email', '')
        )
        password = self._credentials.get('password', '')

        if not username or not password:
            logs.append(
                'Credenciais incompletas: username/email ou password ausente'
            )
            return False

        logs.append('Tentando realizar login automatico')

        try:
            # Timeout granular para login: 30s total (10.2.3)
            return await asyncio.wait_for(
                self._do_login(page, username, password, logs),
                timeout=_LOGIN_TIMEOUT_MS / 1000,
            )
        except asyncio.TimeoutError:
            logs.append(
                f'Timeout no login ({_LOGIN_TIMEOUT_MS / 1000:.0f}s). '
                f'Prosseguindo sem login.'
            )
            return False
        except Exception as e:
            logs.append(f'Erro durante tentativa de login: {str(e)}')
            return False

    async def _do_login(
        self,
        page: 'object',
        username: str,
        password: str,
        logs: list[str],
    ) -> bool:
        """
        Logica interna de login com retry inteligente em cada campo.

        Args:
            page: Instancia da pagina Playwright.
            username: Nome de usuario ou email.
            password: Senha.
            logs: Lista de logs.

        Returns:
            True se o login foi submetido com sucesso.
        """
        # Procura e preenche o campo de username/email
        username_filled = False
        for selector in _USERNAME_SELECTORS:
            try:
                element = page.locator(selector).first
                if await element.is_visible(timeout=2000):
                    await element.fill(username)
                    username_filled = True
                    logs.append(f'Campo de usuario encontrado: {selector}')
                    break
            except Exception:
                continue

        if not username_filled:
            logs.append('Campo de usuario nao encontrado na pagina')
            return False

        # Procura e preenche o campo de password
        password_filled = False
        for selector in _PASSWORD_SELECTORS:
            try:
                element = page.locator(selector).first
                if await element.is_visible(timeout=2000):
                    await element.fill(password)
                    password_filled = True
                    logs.append(f'Campo de senha encontrado: {selector}')
                    break
            except Exception:
                continue

        if not password_filled:
            logs.append('Campo de senha nao encontrado na pagina')
            return False

        # Procura e clica no botao de submit (com retry inteligente)
        submitted = False
        for selector in _SUBMIT_SELECTORS:
            try:
                element = page.locator(selector).first
                if await element.is_visible(timeout=2000):

                    async def _click_submit(
                        sel: str = selector,
                    ) -> None:
                        await page.click(sel, timeout=5000)

                    success = await self._smart_retry(
                        page, _click_submit, max_retries=1, logs=logs,
                    )
                    if success:
                        submitted = True
                        logs.append(
                            f'Botao de login encontrado e clicado: '
                            f'{selector}'
                        )
                        break
            except Exception:
                continue

        if not submitted:
            # Tenta submeter com Enter no campo de senha
            try:
                await page.keyboard.press('Enter')
                submitted = True
                logs.append('Formulario submetido com Enter')
            except Exception:
                logs.append(
                    'Nao foi possivel submeter o formulario de login'
                )
                return False

        # Espera a navegacao apos login
        try:
            await page.wait_for_load_state(
                'domcontentloaded', timeout=10000,
            )
        except Exception:
            pass

        logs.append(f'Login realizado. URL atual: {page.url}')
        return True

    # ------------------------------------------------------------------ #
    #  Screenshot seguro
    # ------------------------------------------------------------------ #

    @staticmethod
    async def _safe_screenshot(page: 'object') -> bytes | None:
        """
        Captura screenshot de forma segura, retornando None em caso de erro.

        Args:
            page: Instancia da pagina Playwright.

        Returns:
            Bytes da imagem PNG ou None se falhar.
        """
        try:
            return await page.screenshot(type='png')
        except Exception as e:
            logger.warning('Erro ao capturar screenshot: %s', str(e))
            return None

    # ------------------------------------------------------------------ #
    #  Prompt assertivo (10.3.1) + Sandbox (10.2.2)
    # ------------------------------------------------------------------ #

    def _build_full_prompt(
        self,
        prompt: str,
        execution_params: dict,
    ) -> str:
        """
        Constroi o prompt completo e assertivo para o agente browser-use.

        Inclui instrucoes numeradas e diretas, regras de screenshots,
        regras de comportamento, restricoes de sandbox e finalizacao
        obrigatoria. Projetado para minimizar loops e navegacao desnecessaria.

        Args:
            prompt: Prompt original do usuario/job.
            execution_params: Parametros adicionais de execucao.

        Returns:
            Prompt completo formatado.
        """
        parts: list[str] = []

        # Identidade e objetivo (direto e assertivo)
        parts.append(
            'Voce e um agente de automacao web. '
            'Siga EXATAMENTE estas instrucoes na ordem:'
        )

        # Step 1: Navegacao
        step_num = 1
        parts.append(f'{step_num}. Navegue para {self._base_url}')
        step_num += 1

        # Step 2: Login (se aplicavel)
        if self._credentials:
            username = (
                self._credentials.get('username')
                or self._credentials.get('email', '')
            )
            if username:
                parts.append(
                    f'{step_num}. Faca login com o email/usuario '
                    f'"{username}" e a senha fornecida'
                )
                step_num += 1

        # Step N: URLs adicionais
        additional_urls = execution_params.get('urls', [])
        if additional_urls:
            urls_str = ', '.join(additional_urls)
            parts.append(
                f'{step_num}. Visite estas URLs adicionais: {urls_str}'
            )
            step_num += 1

        # Step N+1: Instrucoes do usuario
        parts.append(f'{step_num}. {prompt}')
        step_num += 1

        # Step N+2: Extracao de conteudo
        parts.append(
            f'{step_num}. Use a acao "extract" para registrar sua analise '
            f'do que voce esta vendo: conteudo visual, informacoes, '
            f'observacoes importantes e insights'
        )
        step_num += 1

        # Step N+3: Screenshot
        parts.append(
            f'{step_num}. Capture screenshots APENAS dos resultados '
            f'encontrados'
        )
        step_num += 1

        # Step N+4: Finalizar
        parts.append(
            f'{step_num}. Finalize imediatamente apos completar todas as '
            f'instrucoes'
        )

        # Regras de screenshots
        max_screenshots = execution_params.get('max_screenshots', 10)
        parts.append(f'''
REGRAS DE SCREENSHOTS:
- NAO capture screenshots a cada passo intermediario
- Capture APENAS: apos carregar a pagina, apos login, ao encontrar dados solicitados, estado final
- Maximo de {max_screenshots} screenshots

REGRAS DE COMPORTAMENTO:
- NAO explore paginas nao solicitadas
- NAO clique em links nao relacionados a tarefa
- NAO repita acoes ja concluidas
- Se uma acao falhar, tente NO MAXIMO 2 vezes antes de prosseguir
- Se um modal/popup aparecer, feche-o antes de continuar''')

        # Regras de sandbox — injetadas dos execution_params (10.2.2)
        sandbox_rules = execution_params.get('sandbox_rules', '')
        if sandbox_rules:
            parts.append(
                f'\nRESTRICOES DE SEGURANCA:\n{sandbox_rules}'
            )

        # Finalizacao obrigatoria — previne loops
        parts.append('''
FINALIZACAO OBRIGATORIA:
Ao concluir TODAS as instrucoes, sinalize imediatamente com done.
NAO continue navegando. NAO explore secoes adicionais.
Se todas as tentativas de uma acao falharem, prossiga para a proxima instrucao.''')

        return '\n'.join(parts)

    # ------------------------------------------------------------------ #
    #  max_steps dinamico (10.1.4)
    # ------------------------------------------------------------------ #

    def _resolve_max_steps(self, execution_params: dict) -> int:
        """
        Resolve o numero maximo de steps para o agente.

        Prioridade:
        1. execution_params['max_steps'] (definido pelo caller/tasks.py)
        2. self._max_steps (passado no construtor)
        3. Default: 20

        Args:
            execution_params: Parametros de execucao com possivel max_steps.

        Returns:
            Numero maximo de steps.
        """
        if 'max_steps' in execution_params:
            return int(execution_params['max_steps'])
        if self._max_steps is not None:
            return self._max_steps
        return 20

    # ------------------------------------------------------------------ #
    #  Criacao de LLM para browser-use
    # ------------------------------------------------------------------ #

    @staticmethod
    def _create_langchain_llm(llm_config: dict) -> 'object':
        """
        Cria uma instancia de LLM compativel com langchain para uso com browser-use.

        browser-use espera um LLM no formato langchain (ChatOpenAI, ChatAnthropic, etc).

        Args:
            llm_config: Dicionario com configuracao do LLM
                        (provider, model, api_key, temperature).

        Returns:
            Instancia do LLM langchain.

        Raises:
            ValueError: Se o provider nao for suportado.
            ImportError: Se as dependencias necessarias nao estiverem instaladas.
        """
        provider = llm_config.get('provider', 'openai')
        model = llm_config.get('model', 'gpt-4o')
        api_key = llm_config.get('api_key', '')
        temperature = llm_config.get('temperature', 0.7)

        if provider == 'openai':
            try:
                # Usa o ChatOpenAI do browser-use que inclui o atributo 'provider'
                from browser_use import ChatOpenAI
                return ChatOpenAI(
                    model=model,
                    api_key=api_key,
                    temperature=temperature,
                )
            except ImportError:
                from langchain_openai import ChatOpenAI
                return ChatOpenAI(
                    model=model,
                    api_key=api_key,
                    temperature=temperature,
                )

        elif provider == 'anthropic':
            try:
                # Usa o ChatAnthropic do browser-use que inclui o atributo 'provider'
                from browser_use import ChatAnthropic
                return ChatAnthropic(
                    model=model,
                    api_key=api_key,
                    temperature=temperature,
                )
            except ImportError:
                # Fallback para langchain_anthropic
                from langchain_anthropic import ChatAnthropic
                return ChatAnthropic(
                    model=model,
                    api_key=api_key,
                    temperature=temperature,
                )

        elif provider == 'google':
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                return ChatGoogleGenerativeAI(
                    model=model,
                    google_api_key=api_key,
                    temperature=temperature,
                )
            except ImportError:
                raise ImportError(
                    'O pacote "langchain-google-genai" e necessario para '
                    'usar Google com browser-use. '
                    'Instale com: pip install langchain-google-genai'
                )

        else:
            raise ValueError(
                f'Provider LLM "{provider}" nao suportado para browser-use. '
                f'Provedores validos: openai, anthropic, google'
            )
