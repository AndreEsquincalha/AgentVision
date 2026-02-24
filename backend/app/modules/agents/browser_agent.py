import asyncio
import base64
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


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
    faz fallback para Playwright direto com navegacao simples.
    """

    def __init__(
        self,
        base_url: str,
        credentials: dict | None = None,
        headless: bool = True,
        timeout: int = 120,
        timeout_per_step: int = 60,
    ) -> None:
        """
        Inicializa o agente de navegacao.

        Args:
            base_url: URL base do site a ser navegado.
            credentials: Dicionario com credenciais de login (ex: {username: '...', password: '...'}).
            headless: Se True, executa o navegador em modo headless (sem interface grafica).
            timeout: Timeout base em segundos (usado no fallback Playwright).
            timeout_per_step: Timeout maximo por step do agente (segundos).
        """
        self._base_url = base_url
        self._credentials = credentials
        self._headless = headless
        self._timeout = timeout
        self._timeout_per_step = timeout_per_step

    async def run(
        self,
        prompt: str,
        execution_params: dict | None = None,
    ) -> BrowserResult:
        """
        Executa a navegacao guiada pelo prompt.

        Tenta usar browser-use + LLM agent. Se nao for possivel
        (sem LLM configurado ou falha), faz fallback para Playwright direto.

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
                # Fallback para Playwright direto
                return await self._run_with_playwright(
                    prompt=prompt,
                    execution_params=execution_params,
                )
        else:
            # Sem LLM, usa Playwright direto
            return await self._run_with_playwright(
                prompt=prompt,
                execution_params=execution_params,
            )

    async def _run_with_browser_use(
        self,
        prompt: str,
        execution_params: dict,
        llm_config: dict,
    ) -> BrowserResult:
        """
        Executa navegacao usando browser-use com agente de IA.

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

            # Monta o prompt completo com contexto
            full_prompt = self._build_full_prompt(prompt, execution_params)

            logs.append(f'Navegando para {self._base_url}')
            logs.append(f'Prompt: {prompt[:200]}...' if len(prompt) > 200 else f'Prompt: {prompt}')

            # Cria e executa o agente
            agent = Agent(
                task=full_prompt,
                llm=llm,
                browser=browser,
                use_vision=True,
                max_steps=execution_params.get('max_steps', 20),
            )

            # Timeout inteligente: max_steps * timeout_per_step
            # Permite que o agente trabalhe sem ser cortado enquanto progride
            max_steps = execution_params.get('max_steps', 20)
            smart_timeout = float(max_steps * self._timeout_per_step)
            logs.append(f'Timeout: {smart_timeout:.0f}s ({max_steps} steps x {self._timeout_per_step}s/step)')

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
                            logs.append(f'Capturando screenshot #{len(screenshots)}')
                        except Exception as decode_err:
                            logs.append(f'Erro ao decodificar screenshot #{i}: {str(decode_err)}')

            # Extrai URLs visitadas
            visited_urls = history.urls()
            if visited_urls:
                for url in visited_urls:
                    logs.append(f'URL visitada: {url}')

            # Extrai conteudo extraido via acao "extract" durante a navegacao
            extracted_content: list[str] = []
            extracted = history.extracted_content()
            if extracted:
                for content in extracted:
                    if content:
                        content_str = str(content).strip()
                        if content_str:
                            extracted_content.append(content_str)
                            logs.append(f'Conteudo extraido: {content_str[:200]}')

            # Resultado final do agente
            final = history.final_result()
            if final:
                final_str = str(final).strip()
                if final_str:
                    extracted_content.append(final_str)
                    logs.append(f'Resultado final: {final_str[:200]}')

            # Deduplica screenshots (remove prints identicos)
            if len(screenshots) > 1:
                unique_screenshots: list[bytes] = []
                seen_hashes: set[int] = set()
                for img in screenshots:
                    img_hash = hash(img)
                    if img_hash not in seen_hashes:
                        seen_hashes.add(img_hash)
                        unique_screenshots.append(img)
                if len(unique_screenshots) < len(screenshots):
                    logs.append(
                        f'Screenshots deduplicados: {len(screenshots)} -> {len(unique_screenshots)}'
                    )
                    screenshots = unique_screenshots

            # Extrai erros
            errors = history.errors()
            has_errors = False
            if errors:
                for error in errors:
                    if error:
                        has_errors = True
                        logs.append(f'Erro durante navegacao: {str(error)[:200]}')

            is_done = history.is_done()
            logs.append(
                f'Navegacao concluida. Steps: {history.number_of_steps()}, '
                f'Screenshots: {len(screenshots)}, Sucesso: {is_done}'
            )

            return BrowserResult(
                screenshots=screenshots,
                logs=logs,
                extracted_content=extracted_content,
                success=is_done and not has_errors,
                error_message=None if not has_errors else 'Erros encontrados durante navegacao',
            )

        except asyncio.TimeoutError:
            max_steps = execution_params.get('max_steps', 20)
            smart_timeout = max_steps * self._timeout_per_step
            logs.append(f'Timeout atingido ({smart_timeout}s). Capturando screenshot final.')
            # Tenta capturar screenshot final em caso de timeout
            try:
                if browser:
                    session = browser._browser_session if hasattr(browser, '_browser_session') else None
                    if session:
                        final_screenshot = await session.get_screenshot()
                        if final_screenshot:
                            screenshots.append(
                                base64.b64decode(final_screenshot)
                                if isinstance(final_screenshot, str)
                                else final_screenshot
                            )
            except Exception:
                logs.append('Nao foi possivel capturar screenshot final apos timeout')

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
                    logger.warning('Erro ao fechar navegador: %s', str(close_err))

    async def _run_with_playwright(
        self,
        prompt: str,
        execution_params: dict,
    ) -> BrowserResult:
        """
        Executa navegacao usando Playwright diretamente (fallback).

        Navega para a URL base, realiza login se credenciais fornecidas,
        visita URLs adicionais dos parametros e captura screenshots.

        Args:
            prompt: Instrucoes de navegacao (usadas nos logs).
            execution_params: Parametros adicionais (URLs a visitar, wait_time, etc).

        Returns:
            Resultado da navegacao.
        """
        from playwright.async_api import async_playwright

        logs: list[str] = []
        screenshots: list[bytes] = []
        playwright = None
        browser = None

        try:
            logs.append(f'Iniciando Playwright (modo direto) para {self._base_url}')
            logs.append(f'Prompt: {prompt[:200]}...' if len(prompt) > 200 else f'Prompt: {prompt}')

            playwright = await async_playwright().start()
            browser = await playwright.chromium.launch(
                headless=self._headless,
                args=['--no-sandbox', '--disable-setuid-sandbox'],
            )

            context = await browser.new_context(
                viewport={'width': 1280, 'height': 720},
                ignore_https_errors=True,
            )

            # Configura timeout das paginas
            context.set_default_timeout(self._timeout * 1000)

            page = await context.new_page()

            # Navega para a URL base
            logs.append(f'Navegando para {self._base_url}')
            try:
                await page.goto(
                    self._base_url,
                    wait_until='domcontentloaded',
                    timeout=30000,
                )
                logs.append(f'Pagina carregada: {page.url}')
            except Exception as nav_err:
                logs.append(f'Erro na navegacao inicial: {str(nav_err)}')
                # Captura screenshot mesmo em caso de erro
                screenshot = await self._safe_screenshot(page)
                if screenshot:
                    screenshots.append(screenshot)
                    logs.append(f'Capturando screenshot #{len(screenshots)} (erro)')
                return BrowserResult(
                    screenshots=screenshots,
                    logs=logs,
                    success=False,
                    error_message=f'Falha na navegacao para {self._base_url}: {str(nav_err)}',
                )

            # Captura screenshot da pagina inicial
            screenshot = await self._safe_screenshot(page)
            if screenshot:
                screenshots.append(screenshot)
                logs.append(f'Capturando screenshot #{len(screenshots)} (pagina inicial)')

            # Espera opcional antes de continuar
            wait_time = execution_params.get('wait_time', 2)
            await page.wait_for_timeout(int(wait_time * 1000))

            # Tenta login se credenciais fornecidas
            if self._credentials:
                login_success = await self._attempt_login(page, logs)
                if login_success:
                    # Captura screenshot apos login
                    await page.wait_for_timeout(2000)
                    screenshot = await self._safe_screenshot(page)
                    if screenshot:
                        screenshots.append(screenshot)
                        logs.append(f'Capturando screenshot #{len(screenshots)} (apos login)')

            # Visita URLs adicionais se especificadas nos parametros
            additional_urls = execution_params.get('urls', [])
            for url in additional_urls:
                try:
                    # Resolve URL relativa
                    full_url = url if url.startswith('http') else f'{self._base_url.rstrip("/")}/{url.lstrip("/")}'
                    logs.append(f'Navegando para {full_url}')

                    await page.goto(
                        full_url,
                        wait_until='domcontentloaded',
                        timeout=30000,
                    )
                    logs.append(f'Pagina carregada: {page.url}')

                    # Espera a pagina estabilizar
                    await page.wait_for_timeout(int(wait_time * 1000))

                    # Captura screenshot
                    screenshot = await self._safe_screenshot(page)
                    if screenshot:
                        screenshots.append(screenshot)
                        logs.append(f'Capturando screenshot #{len(screenshots)}')

                except Exception as url_err:
                    logs.append(f'Erro ao navegar para {url}: {str(url_err)}')
                    # Captura screenshot do erro
                    screenshot = await self._safe_screenshot(page)
                    if screenshot:
                        screenshots.append(screenshot)
                        logs.append(f'Capturando screenshot #{len(screenshots)} (erro)')

            # Captura screenshot final (full page)
            try:
                final_screenshot = await page.screenshot(
                    full_page=True,
                    type='png',
                )
                screenshots.append(final_screenshot)
                logs.append(f'Capturando screenshot #{len(screenshots)} (pagina completa final)')
            except Exception:
                logs.append('Nao foi possivel capturar screenshot final (full page)')

            # Garante pelo menos um screenshot
            if not screenshots:
                screenshot = await self._safe_screenshot(page)
                if screenshot:
                    screenshots.append(screenshot)
                    logs.append(f'Capturando screenshot #{len(screenshots)} (fallback)')

            logs.append(
                f'Navegacao concluida. Screenshots capturados: {len(screenshots)}'
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
            # Limpeza dos recursos do navegador
            if browser:
                try:
                    await browser.close()
                    logs.append('Navegador fechado com sucesso')
                except Exception as close_err:
                    logger.warning('Erro ao fechar navegador: %s', str(close_err))
            if playwright:
                try:
                    await playwright.stop()
                except Exception:
                    pass

    async def _attempt_login(
        self,
        page: 'object',
        logs: list[str],
    ) -> bool:
        """
        Tenta realizar login na pagina usando as credenciais configuradas.

        Procura por campos comuns de login (email, username, password)
        e tenta preencher e submeter o formulario.

        Args:
            page: Instancia da pagina Playwright.
            logs: Lista de logs para registrar as acoes.

        Returns:
            True se o login foi tentado, False caso contrario.
        """
        if not self._credentials:
            return False

        username = self._credentials.get('username') or self._credentials.get('email', '')
        password = self._credentials.get('password', '')

        if not username or not password:
            logs.append('Credenciais incompletas: username/email ou password ausente')
            return False

        logs.append('Tentando realizar login automatico')

        # Seletores comuns para campos de login
        username_selectors = [
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

        password_selectors = [
            'input[type="password"]',
            'input[name="password"]',
            'input[name="passwd"]',
            'input[name="pass"]',
            'input[id="password"]',
            '#password',
        ]

        submit_selectors = [
            'button[type="submit"]',
            'input[type="submit"]',
            'button:has-text("Login")',
            'button:has-text("Entrar")',
            'button:has-text("Sign in")',
            'button:has-text("Log in")',
            'button:has-text("Submit")',
        ]

        try:
            # Procura e preenche o campo de username/email
            username_filled = False
            for selector in username_selectors:
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
            for selector in password_selectors:
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

            # Procura e clica no botao de submit
            submitted = False
            for selector in submit_selectors:
                try:
                    element = page.locator(selector).first
                    if await element.is_visible(timeout=2000):
                        await element.click()
                        submitted = True
                        logs.append(f'Botao de login encontrado e clicado: {selector}')
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
                    logs.append('Nao foi possivel submeter o formulario de login')
                    return False

            # Espera a navegacao apos login
            try:
                await page.wait_for_load_state('domcontentloaded', timeout=10000)
            except Exception:
                pass

            logs.append(f'Login realizado. URL atual: {page.url}')
            return True

        except Exception as e:
            logs.append(f'Erro durante tentativa de login: {str(e)}')
            return False

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

    def _build_full_prompt(
        self,
        prompt: str,
        execution_params: dict,
    ) -> str:
        """
        Constroi o prompt completo para o agente browser-use.

        Inclui a URL base, instrucoes de login se necessario,
        e parametros adicionais.

        Args:
            prompt: Prompt original do usuario/job.
            execution_params: Parametros adicionais de execucao.

        Returns:
            Prompt completo formatado.
        """
        parts: list[str] = []

        # URL base
        parts.append(f'Navegue para {self._base_url}.')

        # Instrucoes de login
        if self._credentials:
            username = self._credentials.get('username') or self._credentials.get('email', '')
            if username:
                parts.append(
                    f'Faca login usando o email/usuario "{username}" e a senha fornecida.'
                )

        # URLs adicionais
        additional_urls = execution_params.get('urls', [])
        if additional_urls:
            parts.append(
                f'Depois visite estas URLs adicionais: {", ".join(additional_urls)}.'
            )

        # Prompt principal
        parts.append(f'Instrucoes: {prompt}')

        # Instrucao para capturar screenshots e extrair conteudo
        parts.append(
            'Capture screenshots nos momentos relevantes (apos carregar paginas, '
            'apos interacoes importantes, e quando encontrar informacoes relevantes). '
            'Enquanto navega, use a acao "extract" para extrair e registrar sua analise '
            'do que voce esta vendo: descreva o conteudo visual, informacoes encontradas, '
            'observacoes importantes e insights. Essa analise sera usada no relatorio final.'
        )

        # Instrucao de finalizacao — evita que o agente fique em loop apos completar a tarefa
        parts.append(
            'IMPORTANTE: Quando voce tiver concluido todas as instrucoes acima e '
            'capturado os screenshots necessarios, pare imediatamente. '
            'Nao continue navegando, nao explore outras secoes do site, '
            'nao repita acoes ja concluidas. Sinalize que a tarefa foi concluida com done.'
        )

        return ' '.join(parts)

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
                from langchain_openai import ChatOpenAI
                return ChatOpenAI(
                    model=model,
                    api_key=api_key,
                    temperature=temperature,
                )
            except ImportError:
                # Fallback: tenta usar ChatOpenAI do browser-use
                from browser_use import ChatOpenAI
                return ChatOpenAI(
                    model=model,
                    api_key=api_key,
                    temperature=temperature,
                )

        elif provider == 'anthropic':
            try:
                from langchain_anthropic import ChatAnthropic
                return ChatAnthropic(
                    model=model,
                    api_key=api_key,
                    temperature=temperature,
                )
            except ImportError:
                raise ImportError(
                    'O pacote "langchain-anthropic" e necessario para usar Anthropic com browser-use. '
                    'Instale com: pip install langchain-anthropic'
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
                    'O pacote "langchain-google-genai" e necessario para usar Google com browser-use. '
                    'Instale com: pip install langchain-google-genai'
                )

        else:
            raise ValueError(
                f'Provider LLM "{provider}" nao suportado para browser-use. '
                f'Provedores validos: openai, anthropic, google'
            )
