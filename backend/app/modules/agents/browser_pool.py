"""
Pool de browser contexts Playwright para reutilizacao entre execucoes.

Em vez de criar e destruir browser + context a cada execucao (~3s overhead),
o pool mantem instancias pre-inicializadas e faz reset de estado entre usos,
reduzindo o tempo de startup para ~0.5s.
"""

import asyncio
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# Tamanho default do pool
_DEFAULT_POOL_SIZE: int = 3

# Maximo de reutilizacoes antes de reciclar o browser (evita memory leaks)
_MAX_REUSES: int = 20


@dataclass
class _PooledBrowser:
    """Wrapper de uma instancia Playwright + browser do pool."""
    playwright: object = None
    browser: object = None
    reuse_count: int = 0
    in_use: bool = False


class BrowserContextPool:
    """
    Pool de instancias Playwright para reutilizacao.

    Cada instancia no pool consiste de um Playwright instance + browser.
    Ao adquirir, um novo context e criado (com estado limpo).
    Ao liberar, o context e fechado mas o browser permanece aberto.

    Uso:
        pool = BrowserContextPool(pool_size=3, headless=True)
        await pool.initialize()

        context, page, pooled = await pool.acquire()
        # ... usar page para navegacao ...
        await pool.release(pooled, context)

        await pool.shutdown()
    """

    def __init__(
        self,
        pool_size: int = _DEFAULT_POOL_SIZE,
        headless: bool = True,
    ) -> None:
        self._pool_size = pool_size
        self._headless = headless
        self._pool: list[_PooledBrowser] = []
        self._lock = asyncio.Lock()
        self._initialized = False

    async def initialize(self) -> None:
        """Pre-inicializa as instancias do pool."""
        if self._initialized:
            return

        async with self._lock:
            if self._initialized:
                return

            for i in range(self._pool_size):
                try:
                    pooled = await self._create_browser()
                    self._pool.append(pooled)
                    logger.info(
                        'Browser pool: instancia %d/%d inicializada',
                        i + 1, self._pool_size,
                    )
                except Exception as e:
                    logger.warning(
                        'Browser pool: falha ao inicializar instancia %d: %s',
                        i + 1, str(e),
                    )

            self._initialized = True
            logger.info(
                'Browser pool inicializado com %d instancia(s)',
                len(self._pool),
            )

    async def _create_browser(self) -> _PooledBrowser:
        """Cria uma nova instancia Playwright + browser."""
        from playwright.async_api import async_playwright

        pw = await async_playwright().start()
        browser = await pw.chromium.launch(
            headless=self._headless,
            args=['--no-sandbox', '--disable-setuid-sandbox'],
        )
        return _PooledBrowser(playwright=pw, browser=browser)

    async def acquire(
        self,
        viewport: dict | None = None,
        timeout_ms: int = 120_000,
    ) -> tuple[object, object, _PooledBrowser]:
        """
        Adquire um browser do pool e cria um context limpo.

        Args:
            viewport: Dimensoes do viewport (default: 1280x720).
            timeout_ms: Timeout padrao para o context.

        Returns:
            Tupla (context, page, pooled_browser).
            O pooled_browser deve ser passado para release().
        """
        viewport = viewport or {'width': 1280, 'height': 720}

        async with self._lock:
            # Busca instancia disponivel no pool
            for pooled in self._pool:
                if not pooled.in_use:
                    # Verifica se precisa reciclar (muitas reutilizacoes)
                    if pooled.reuse_count >= _MAX_REUSES:
                        await self._recycle_browser(pooled)

                    pooled.in_use = True
                    pooled.reuse_count += 1
                    break
            else:
                # Pool cheio, cria instancia temporaria
                logger.debug(
                    'Browser pool cheio (%d em uso), criando instancia temporaria',
                    len(self._pool),
                )
                pooled = await self._create_browser()
                pooled.in_use = True
                pooled.reuse_count = 1

        # Cria context limpo (fora do lock para nao bloquear o pool)
        context = await pooled.browser.new_context(
            viewport=viewport,
            ignore_https_errors=True,
        )
        context.set_default_timeout(timeout_ms)
        page = await context.new_page()

        return context, page, pooled

    async def release(
        self,
        pooled: _PooledBrowser,
        context: object,
    ) -> None:
        """
        Libera o browser de volta ao pool e fecha o context.

        Args:
            pooled: Instancia do pool a liberar.
            context: Context Playwright a ser fechado.
        """
        # Fecha o context (limpa cookies, cache, localStorage)
        try:
            await context.close()
        except Exception as e:
            logger.debug('Erro ao fechar context: %s', str(e))

        async with self._lock:
            if pooled in self._pool:
                pooled.in_use = False
            else:
                # Instancia temporaria — fecha completamente
                await self._close_browser(pooled)

    async def _recycle_browser(self, pooled: _PooledBrowser) -> None:
        """Recicla uma instancia do pool (fecha e recria)."""
        try:
            await self._close_browser(pooled)
        except Exception:
            pass

        try:
            new = await self._create_browser()
            pooled.playwright = new.playwright
            pooled.browser = new.browser
            pooled.reuse_count = 0
            logger.debug('Browser pool: instancia reciclada')
        except Exception as e:
            logger.warning('Browser pool: falha ao reciclar instancia: %s', str(e))

    async def _close_browser(self, pooled: _PooledBrowser) -> None:
        """Fecha browser e para Playwright de forma segura."""
        if pooled.browser:
            try:
                await pooled.browser.close()
            except Exception:
                pass
        if pooled.playwright:
            try:
                await pooled.playwright.stop()
            except Exception:
                pass

    async def shutdown(self) -> None:
        """Fecha todas as instancias do pool."""
        async with self._lock:
            for pooled in self._pool:
                await self._close_browser(pooled)
            self._pool.clear()
            self._initialized = False
            logger.info('Browser pool encerrado')

    @property
    def stats(self) -> dict:
        """Retorna estatisticas do pool."""
        in_use = sum(1 for p in self._pool if p.in_use)
        return {
            'pool_size': len(self._pool),
            'in_use': in_use,
            'available': len(self._pool) - in_use,
            'initialized': self._initialized,
        }


# ---------------------------------------------------------------------------
# Singleton global do pool (inicializado lazy no primeiro uso)
# ---------------------------------------------------------------------------
_global_pool: BrowserContextPool | None = None
_global_pool_lock = asyncio.Lock()


async def get_browser_pool(
    pool_size: int = _DEFAULT_POOL_SIZE,
    headless: bool = True,
) -> BrowserContextPool:
    """
    Retorna o pool global de browsers (singleton).

    Inicializa no primeiro uso. Chamadas subsequentes retornam a mesma instancia.
    """
    global _global_pool

    if _global_pool is not None and _global_pool._initialized:
        return _global_pool

    async with _global_pool_lock:
        if _global_pool is None or not _global_pool._initialized:
            _global_pool = BrowserContextPool(
                pool_size=pool_size,
                headless=headless,
            )
            await _global_pool.initialize()

    return _global_pool
