import asyncio
import json
import logging
import threading
import traceback
import uuid
from datetime import timedelta

from croniter import croniter
from redis import Redis

from app.celery_app import celery_app
from app.config import settings
from app.database import SessionLocal
from app.shared.utils import utc_now

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes de configuracao para controle de execucoes
# ---------------------------------------------------------------------------

# Timeout padrao por step do agente (segundos)
_DEFAULT_TIMEOUT_PER_STEP: int = 30

# Numero padrao de steps do agente
_DEFAULT_MAX_STEPS: int = 25

# Margem de seguranca adicional para o lock (segundos)
_LOCK_SAFETY_MARGIN: int = 120

# Tempo maximo (minutos) para considerar uma execucao running como orfa
_STALE_EXECUTION_THRESHOLD_MINUTES: int = 30

# Intervalo de heartbeat (segundos)
_HEARTBEAT_INTERVAL_SECONDS: int = 30

# Maximo de execucoes simultaneas (semaforo global)
_DEFAULT_MAX_CONCURRENT_JOBS: int = 3

# Tempo de retry quando semaforo esta cheio (segundos)
_SEMAPHORE_RETRY_COUNTDOWN: int = 30

# Prefixo das chaves Redis
_LOCK_KEY_PREFIX: str = 'job_lock:'
_SEMAPHORE_KEY: str = 'execution_semaphore'

# URL base do frontend para links em notificacoes
_FRONTEND_BASE_URL: str = 'http://localhost:3000'


# ---------------------------------------------------------------------------
# Hierarquia de erros para recuperacao granular (11.3.1)
# ---------------------------------------------------------------------------

class FatalExecutionError(Exception):
    """
    Erro FATAL: impossivel continuar a execucao.

    Ex: browser nao inicia, URL inacessivel, validacao falha.
    Resultado: execucao marcada como 'failed'.
    """
    pass


class CriticalExecutionError(Exception):
    """
    Erro CRITICO: falha grave mas execucao pode continuar parcialmente.

    Ex: login falha, mas ainda pode capturar screenshots da pagina publica.
    Resultado: execucao continua com aviso.
    """
    pass


# ---------------------------------------------------------------------------
# Helpers: Redis client
# ---------------------------------------------------------------------------

def _get_redis_client() -> Redis:
    """Retorna uma instancia do cliente Redis usando a URL das configuracoes."""
    return Redis.from_url(settings.redis_url, decode_responses=True)


# ---------------------------------------------------------------------------
# Helpers: Distributed Lock com Redis
# ---------------------------------------------------------------------------

def _acquire_lock(
    redis_client: Redis,
    job_id: str,
    lock_token: str,
    ttl_seconds: int,
) -> bool:
    """
    Tenta adquirir um lock distribuido para o job via Redis SET NX EX.

    Args:
        redis_client: Cliente Redis.
        job_id: ID do job (string UUID).
        lock_token: Token UUID unico para identificar o dono do lock.
        ttl_seconds: Tempo de vida do lock em segundos.

    Returns:
        True se o lock foi adquirido, False caso contrario.
    """
    lock_key = f'{_LOCK_KEY_PREFIX}{job_id}'
    acquired: bool | None = redis_client.set(
        lock_key, lock_token, nx=True, ex=ttl_seconds,
    )
    return acquired is True


def _release_lock(
    redis_client: Redis,
    job_id: str,
    lock_token: str,
) -> bool:
    """
    Libera o lock distribuido, verificando ownership via token UUID.

    Usa um script Lua atomico para garantir que apenas o dono do lock
    pode libera-lo (evita liberar lock de outro processo).

    Args:
        redis_client: Cliente Redis.
        job_id: ID do job (string UUID).
        lock_token: Token UUID do dono do lock.

    Returns:
        True se o lock foi liberado, False caso contrario.
    """
    lock_key = f'{_LOCK_KEY_PREFIX}{job_id}'

    # Script Lua atomico: verifica ownership antes de deletar
    lua_script = """
    if redis.call('get', KEYS[1]) == ARGV[1] then
        return redis.call('del', KEYS[1])
    else
        return 0
    end
    """
    result = redis_client.eval(lua_script, 1, lock_key, lock_token)
    return result == 1


def _force_release_lock(redis_client: Redis, job_id: str) -> bool:
    """
    Forca a liberacao do lock de um job (usado pelo cleanup de execucoes orfas).

    Args:
        redis_client: Cliente Redis.
        job_id: ID do job (string UUID).

    Returns:
        True se o lock existia e foi removido, False caso contrario.
    """
    lock_key = f'{_LOCK_KEY_PREFIX}{job_id}'
    result: int = redis_client.delete(lock_key)
    return result > 0


# ---------------------------------------------------------------------------
# Helpers: Semaforo Redis para limite global de concorrencia
# ---------------------------------------------------------------------------

def _acquire_semaphore(redis_client: Redis, max_concurrent: int) -> bool:
    """
    Tenta adquirir uma vaga no semaforo global de execucoes.

    Usa INCR atomico e verifica se o valor esta dentro do limite.
    Se excedeu, faz DECR para reverter.

    Args:
        redis_client: Cliente Redis.
        max_concurrent: Numero maximo de execucoes simultaneas.

    Returns:
        True se a vaga foi adquirida, False se o limite foi atingido.
    """
    current: int = redis_client.incr(_SEMAPHORE_KEY)

    if current <= max_concurrent:
        return True

    # Excedeu o limite: reverte o INCR
    redis_client.decr(_SEMAPHORE_KEY)
    return False


def _release_semaphore(redis_client: Redis) -> None:
    """
    Libera uma vaga no semaforo global de execucoes.

    Usa DECR atomico e garante que nao fique negativo.

    Args:
        redis_client: Cliente Redis.
    """
    current: int = redis_client.decr(_SEMAPHORE_KEY)

    # Protecao: se ficou negativo (bug ou restart), corrige para zero
    if current < 0:
        redis_client.set(_SEMAPHORE_KEY, 0)


def _get_max_concurrent_jobs() -> int:
    """
    Obtem o limite de execucoes simultaneas da tabela Settings.

    Fallback para o valor padrao se nao encontrado no banco.

    Returns:
        Numero maximo de execucoes simultaneas permitidas.
    """
    try:
        db = SessionLocal()
        try:
            from app.modules.settings.models import Setting  # noqa: F401
            from sqlalchemy import select

            stmt = select(Setting).where(Setting.key == 'execution.max_concurrent_jobs')
            setting = db.execute(stmt).scalar_one_or_none()

            if setting and setting.encrypted_value:
                from app.shared.utils import decrypt_value
                value = decrypt_value(setting.encrypted_value)
                return int(value)
        finally:
            db.close()
    except Exception as e:
        logger.debug(
            'Nao foi possivel ler max_concurrent_jobs do banco: %s. '
            'Usando valor padrao: %d', str(e), _DEFAULT_MAX_CONCURRENT_JOBS,
        )

    return _DEFAULT_MAX_CONCURRENT_JOBS


# ---------------------------------------------------------------------------
# Helper: Calculo do TTL do lock
# ---------------------------------------------------------------------------

def _calculate_lock_ttl(execution_params: dict | None) -> int:
    """
    Calcula o TTL do lock baseado nos parametros de execucao do job.

    Formula: max_steps * timeout_per_step + margem de seguranca.

    Args:
        execution_params: Parametros de execucao do job (pode ser None).

    Returns:
        TTL em segundos.
    """
    params = execution_params or {}
    max_steps = params.get('max_steps', _DEFAULT_MAX_STEPS)
    timeout_per_step = params.get('timeout_per_step', _DEFAULT_TIMEOUT_PER_STEP)
    ttl = (max_steps * timeout_per_step) + _LOCK_SAFETY_MARGIN
    return ttl


# ---------------------------------------------------------------------------
# Helper: Heartbeat daemon thread
# ---------------------------------------------------------------------------

class _HeartbeatThread:
    """
    Thread daemon que atualiza o campo last_heartbeat no banco periodicamente.

    Usa sua propria sessao DB (nao compartilha com a task principal)
    para evitar interferencia com as transacoes da task.
    """

    def __init__(
        self,
        execution_id: uuid.UUID,
        interval_seconds: int = _HEARTBEAT_INTERVAL_SECONDS,
    ) -> None:
        self._execution_id = execution_id
        self._interval = interval_seconds
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Inicia a thread daemon de heartbeat."""
        self._thread = threading.Thread(
            target=self._heartbeat_loop,
            daemon=True,
            name=f'heartbeat-{self._execution_id}',
        )
        self._thread.start()
        logger.debug(
            'Heartbeat thread iniciada para execution %s (intervalo=%ds)',
            str(self._execution_id), self._interval,
        )

    def stop(self) -> None:
        """Para a thread de heartbeat de forma graceful."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.debug(
            'Heartbeat thread parada para execution %s',
            str(self._execution_id),
        )

    def _heartbeat_loop(self) -> None:
        """Loop principal da thread: atualiza last_heartbeat a cada intervalo."""
        while not self._stop_event.is_set():
            # Aguarda pelo intervalo ou ate ser sinalizado para parar
            if self._stop_event.wait(timeout=self._interval):
                break

            # Usa sessao propria para nao interferir na task principal
            db = SessionLocal()
            try:
                from app.modules.executions.models import Execution
                from sqlalchemy import select

                now = utc_now()
                stmt = select(Execution).where(
                    Execution.id == self._execution_id,
                )
                execution = db.execute(stmt).scalar_one_or_none()

                if execution and execution.status == 'running':
                    execution.last_heartbeat = now
                    db.commit()
                    logger.debug(
                        'Heartbeat atualizado para execution %s em %s',
                        str(self._execution_id), now.isoformat(),
                    )
                else:
                    # Execucao nao existe mais ou nao esta running; para o heartbeat
                    logger.debug(
                        'Heartbeat encerrado: execution %s nao esta mais running',
                        str(self._execution_id),
                    )
                    break
            except Exception as e:
                logger.warning(
                    'Erro ao atualizar heartbeat da execution %s: %s',
                    str(self._execution_id), str(e),
                )
            finally:
                db.close()


# ---------------------------------------------------------------------------
# Helper: Calculo dinamico de max_steps baseado na complexidade
# ---------------------------------------------------------------------------

def _calculate_max_steps(
    prompt: str,
    credentials: dict | None,
    exec_params: dict,
) -> int:
    """
    Calcula max_steps dinamico baseado na complexidade da tarefa.

    Se o usuario definiu explicitamente max_steps nos parametros
    de execucao, esse valor e respeitado. Caso contrario, aplica
    heuristicas baseadas no prompt e contexto da execucao.

    Args:
        prompt: Prompt do agente (usado para detectar complexidade).
        credentials: Credenciais de acesso (indica necessidade de login).
        exec_params: Parametros de execucao do job.

    Returns:
        Numero de max_steps calculado.
    """
    # Se o usuario definiu explicitamente, respeitar
    explicit_max_steps = exec_params.get('max_steps')
    if explicit_max_steps:
        return int(explicit_max_steps)

    has_login = credentials is not None
    has_additional_urls = bool(exec_params.get('urls'))
    prompt_lower = prompt.lower()

    # Heuristicas de complexidade baseadas em palavras-chave do prompt
    is_complex = any(kw in prompt_lower for kw in [
        'extrair', 'extract', 'preencher', 'fill', 'formulario', 'form',
        'tabela', 'table', 'dados', 'data', 'buscar', 'search',
    ])

    if is_complex:
        return 25
    elif has_login and has_additional_urls:
        return 15
    elif has_login:
        return 10
    else:
        return 5


# ---------------------------------------------------------------------------
# Helper: Atualiza progresso da execucao no banco (11.3.2)
# ---------------------------------------------------------------------------

def _update_progress(
    execution_id: uuid.UUID,
    progress_percent: int,
    db_session: 'Session | None' = None,
) -> None:
    """
    Atualiza o progresso percentual de uma execucao.

    Usa a sessao fornecida ou cria uma propria. Erros sao ignorados
    (logging apenas) para nao interromper a execucao.

    Args:
        execution_id: ID da execucao.
        progress_percent: Percentual de progresso (0-100).
        db_session: Sessao do banco (opcional; cria uma nova se None).
    """
    own_session = db_session is None
    db = db_session or SessionLocal()
    try:
        from app.modules.executions.models import Execution
        from sqlalchemy import select

        stmt = select(Execution).where(Execution.id == execution_id)
        execution = db.execute(stmt).scalar_one_or_none()
        if execution:
            execution.progress_percent = max(0, min(100, progress_percent))
            db.commit()
    except Exception as e:
        logger.debug(
            'Erro ao atualizar progresso da execution %s: %s',
            str(execution_id), str(e),
        )
    finally:
        if own_session:
            db.close()


# ---------------------------------------------------------------------------
# Helper: Notificacao de falha critica (11.3.4)
# ---------------------------------------------------------------------------

def send_failure_notification(
    job_id: uuid.UUID,
    job_name: str,
    execution_id: uuid.UUID,
    error_message: str,
    notify_on_failure: bool,
) -> None:
    """
    Envia notificacao de falha de execucao pelos canais configurados.

    Verifica se o job tem notify_on_failure ativo e se existem delivery configs
    ativos. Se sim, envia uma notificacao de alerta por cada canal.

    Args:
        job_id: ID do job que falhou.
        job_name: Nome do job.
        execution_id: ID da execucao que falhou.
        error_message: Mensagem de erro da falha.
        notify_on_failure: Se o job tem notificacao de falha ativa.
    """
    if not notify_on_failure:
        logger.debug(
            'Notificacao de falha desabilitada para job %s', str(job_id),
        )
        return

    db = SessionLocal()
    try:
        from app.modules.delivery.models import DeliveryConfig  # noqa: F401
        from app.modules.delivery.repository import DeliveryRepository
        from app.modules.delivery.service import DeliveryService

        delivery_repo = DeliveryRepository(db)
        delivery_service = DeliveryService(delivery_repo)

        # Busca configuracoes de entrega ativas
        active_configs = delivery_repo.get_active_configs_by_job(job_id)

        if not active_configs:
            logger.debug(
                'Sem delivery configs ativos para notificacao de falha do job %s',
                str(job_id),
            )
            return

        # Monta dados da notificacao de falha
        now = utc_now()
        execution_url = (
            f'{_FRONTEND_BASE_URL}/executions/{execution_id}'
        )

        execution_data: dict = {
            'job_name': job_name,
            'execution_date': now.isoformat(),
            'summary': (
                f'FALHA NA EXECUCAO\n\n'
                f'Job: {job_name}\n'
                f'Execution ID: {execution_id}\n'
                f'Erro: {error_message[:500]}\n'
                f'Data: {now.strftime("%d/%m/%Y %H:%M:%S UTC")}\n\n'
                f'Acesse os detalhes: {execution_url}'
            ),
        }

        delivery_service.deliver(
            execution_id=execution_id,
            delivery_configs=active_configs,
            pdf_path=None,
            execution_data=execution_data,
        )

        logger.info(
            'Notificacao de falha enviada para job %s (execution=%s, canais=%d)',
            str(job_id), str(execution_id), len(active_configs),
        )

    except Exception as e:
        # Notificacao de falha e best-effort; nao deve impedir o fluxo
        logger.warning(
            'Erro ao enviar notificacao de falha para job %s: %s',
            str(job_id), str(e),
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Task principal: execute_job (11.3.1 — recuperacao granular)
# ---------------------------------------------------------------------------

@celery_app.task(
    bind=True,
    name='app.modules.jobs.tasks.execute_job',
    max_retries=3,
    default_retry_delay=_SEMAPHORE_RETRY_COUNTDOWN,
)
def execute_job(self, job_id: str, is_dry_run: bool = False) -> dict:
    """
    Task Celery que executa o fluxo completo de um job.

    Inclui controles de concorrencia:
    - Distributed lock Redis (previne execucoes duplicadas do mesmo job)
    - Semaforo global Redis (limita execucoes simultaneas)
    - Heartbeat thread (prova de vida para deteccao de execucoes orfas)
    - Registro de celery_task_id para correlacao

    Recuperacao granular por fase (11.3.1):
    - FATAL: browser nao inicia, URL inacessivel -> para e marca como failed
    - CRITICAL: login falha -> continua sem login
    - WARNING: LLM falha -> gera PDF sem analise
    - INFO: delivery falha -> execucao e success (delivery e best-effort)

    Progresso parcial (11.3.2):
    - 10%: Execution criada
    - 20%: Browser iniciado
    - 40%: Navegacao concluida
    - 60%: Screenshots salvos
    - 75%: Analise LLM concluida
    - 90%: PDF gerado
    - 100%: Entrega concluida / finalizado

    Args:
        self: Instancia da task (bind=True).
        job_id: ID do job a ser executado (string UUID).
        is_dry_run: Se True, pula a etapa de entrega.

    Returns:
        Dicionario com resultado da execucao.
    """
    # Importa o ExecutionLogger para logs estruturados (11.3.3)
    from app.modules.executions.log_utils import ExecutionLogger

    redis_client = _get_redis_client()
    lock_token = str(uuid.uuid4())
    lock_acquired = False
    semaphore_acquired = False
    heartbeat: _HeartbeatThread | None = None

    job_uuid = uuid.UUID(job_id)
    execution_id: uuid.UUID | None = None
    started_at = None
    exec_logger = ExecutionLogger()
    db = SessionLocal()

    # Variaveis extraidas do job para uso ao longo da task
    job_name: str = ''
    notify_on_failure: bool = True

    try:
        # -----------------------------------------------------------------
        # 0a. Adquire semaforo global de concorrencia
        # -----------------------------------------------------------------
        max_concurrent = _get_max_concurrent_jobs()
        semaphore_acquired = _acquire_semaphore(redis_client, max_concurrent)

        if not semaphore_acquired:
            logger.info(
                'Semaforo de execucoes cheio (%d/%d). '
                'Reenfileirando job %s com countdown de %ds.',
                max_concurrent, max_concurrent, job_id,
                _SEMAPHORE_RETRY_COUNTDOWN,
            )
            # Reenfileira a task com countdown para tentar novamente
            raise self.retry(
                countdown=_SEMAPHORE_RETRY_COUNTDOWN,
                exc=Exception(
                    f'Semaforo cheio ({max_concurrent} execucoes simultaneas). '
                    f'Tentando novamente em {_SEMAPHORE_RETRY_COUNTDOWN}s.'
                ),
            )

        logger.info(
            'Semaforo adquirido para job %s', job_id,
        )

        # -----------------------------------------------------------------
        # 0b. Adquire lock distribuido para o job
        # -----------------------------------------------------------------
        # Busca execution_params do job para calcular TTL do lock
        from app.modules.jobs.models import Job as JobModel
        from sqlalchemy import select as sa_select

        stmt = sa_select(JobModel).where(JobModel.id == job_uuid)
        job_for_ttl = db.execute(stmt).scalar_one_or_none()
        execution_params_for_ttl = (
            dict(job_for_ttl.execution_params)
            if job_for_ttl and job_for_ttl.execution_params
            else None
        )
        if job_for_ttl:
            db.expunge(job_for_ttl)

        lock_ttl = _calculate_lock_ttl(execution_params_for_ttl)
        lock_acquired = _acquire_lock(redis_client, job_id, lock_token, lock_ttl)

        if not lock_acquired:
            logger.info(
                'Job %s ja esta em execucao (lock nao adquirido). Pulando.',
                job_id,
            )
            # Libera semaforo ja que nao vai executar
            _release_semaphore(redis_client)
            semaphore_acquired = False
            return {
                'success': False,
                'job_id': job_id,
                'error': f'Job {job_id} ja esta em execucao (lock distribuido ativo)',
                'skipped': True,
            }

        logger.info(
            'Lock adquirido para job %s (token=%s, ttl=%ds)',
            job_id, lock_token[:8], lock_ttl,
        )

        # -----------------------------------------------------------------
        # 1. Busca o Job com projeto e delivery configs
        # -----------------------------------------------------------------
        logger.info(
            'Iniciando execucao do job %s (dry_run=%s, task_id=%s)',
            job_id, is_dry_run, self.request.id,
        )

        # Importa todos os modelos para garantir que o SQLAlchemy resolva relacionamentos
        from app.modules.jobs.models import Job  # noqa: F811
        from app.modules.projects.models import Project  # noqa: F401
        from app.modules.executions.models import Execution  # noqa: F401
        from app.modules.delivery.models import DeliveryConfig, DeliveryLog  # noqa: F401
        from app.modules.prompts.models import PromptTemplate  # noqa: F401
        from app.modules.jobs.repository import JobRepository
        from app.modules.projects.repository import ProjectRepository
        from app.modules.projects.service import ProjectService
        from app.modules.executions.repository import ExecutionRepository
        from app.modules.delivery.repository import DeliveryRepository
        from app.modules.delivery.service import DeliveryService

        job_repo = JobRepository(db)
        project_repo = ProjectRepository(db)
        project_service = ProjectService(project_repo)
        execution_repo = ExecutionRepository(db)
        delivery_repo = DeliveryRepository(db)
        delivery_service = DeliveryService(delivery_repo)

        job = job_repo.get_by_id(job_uuid)
        if not job:
            error_msg = f'Job {job_id} nao encontrado'
            logger.error(error_msg)
            return {'success': False, 'error': error_msg}

        project = job.project
        if not project:
            error_msg = f'Projeto nao encontrado para o job {job_id}'
            logger.error(error_msg)
            return {'success': False, 'error': error_msg}

        # Extrai dados do job e projeto em variaveis locais para evitar
        # que o SQLAlchemy persista alteracoes acidentais nos objetos
        # durante os commits subsequentes da sessao (BUG-006).
        job_name = job.name
        job_agent_prompt: str = job.agent_prompt
        job_execution_params: dict | None = (
            dict(job.execution_params) if job.execution_params else None
        )
        notify_on_failure = getattr(job, 'notify_on_failure', True)
        if notify_on_failure is None:
            notify_on_failure = True

        project_name: str = project.name
        project_base_url: str = project.base_url
        project_id: uuid.UUID = project.id

        # Remove o Job e o Project do rastreamento da sessao para
        # garantir que nenhum commit subsequente altere seus dados.
        db.expunge(job)
        db.expunge(project)

        logger.info(
            'Job encontrado: %s (projeto: %s, URL: %s)',
            job_name, project_name, project_base_url,
        )

        # -----------------------------------------------------------------
        # 2. Cria registro de Execution (status=pending, com celery_task_id)
        # -----------------------------------------------------------------
        execution = execution_repo.create({
            'job_id': job_uuid,
            'status': 'pending',
            'is_dry_run': is_dry_run,
            'celery_task_id': self.request.id,
        })
        execution_id = execution.id
        logger.info(
            'Execution criada: %s (status=pending, celery_task_id=%s)',
            str(execution_id), self.request.id,
        )

        # Progresso: 10% — execucao criada
        _update_progress(execution_id, 10, db)

        # -----------------------------------------------------------------
        # 3. Atualiza para running, registra started_at e inicia heartbeat
        # -----------------------------------------------------------------
        started_at = utc_now()
        execution_repo.update_status(
            execution_id=execution_id,
            status='running',
            started_at=started_at,
        )

        # Atualiza o primeiro heartbeat
        _update_heartbeat_directly(execution_id)

        # Inicia thread daemon de heartbeat
        heartbeat = _HeartbeatThread(execution_id)
        heartbeat.start()

        logger.info('Execution %s atualizada para running', str(execution_id))

        exec_logger.info('setup', f'Iniciando execucao do job "{job_name}"')
        exec_logger.info('setup', f'Projeto: {project_name} | URL: {project_base_url}')
        exec_logger.info('setup', f'Dry run: {is_dry_run}')
        exec_logger.info('setup', f'Task ID: {self.request.id}')

        # -----------------------------------------------------------------
        # 4. Obtem credenciais e configuracao LLM do projeto
        # -----------------------------------------------------------------
        credentials: dict | None = None
        try:
            credentials = project_service.get_decrypted_credentials(project_id)
            if credentials:
                exec_logger.info('setup', 'Credenciais do projeto carregadas com sucesso')
            else:
                exec_logger.info('setup', 'Projeto sem credenciais configuradas')
        except Exception as e:
            exec_logger.warning(
                'setup',
                f'Nao foi possivel carregar credenciais: {str(e)}',
                {'error_type': type(e).__name__},
            )
            logger.warning('Falha ao carregar credenciais do projeto %s: %s', project_id, str(e))

        llm_config: dict = {}
        try:
            llm_config = project_service.get_llm_config(project_id)
            exec_logger.info(
                'setup',
                f'LLM configurado: {llm_config.get("provider")} / {llm_config.get("model")}',
            )
        except Exception as e:
            exec_logger.warning(
                'setup',
                f'Nao foi possivel carregar config LLM: {str(e)}',
                {'error_type': type(e).__name__},
            )
            logger.warning('Falha ao carregar config LLM do projeto %s: %s', project_id, str(e))

        # -----------------------------------------------------------------
        # 4.5. Validacao pre-execucao
        # -----------------------------------------------------------------
        from app.modules.agents.execution_validator import ExecutionValidator

        validation = ExecutionValidator.validate(
            base_url=project_base_url,
            credentials=credentials,
            llm_config=llm_config,
        )

        for warning in validation.warnings:
            exec_logger.warning('setup', f'Aviso de validacao: {warning}')

        if not validation.is_valid:
            for error in validation.errors:
                exec_logger.fatal('setup', f'Erro de validacao: {error}')

            logger.warning(
                'Validacao pre-execucao falhou para job %s: %s',
                job_id, '; '.join(validation.errors),
            )

            # FATAL: validacao falhou, impossivel prosseguir
            raise FatalExecutionError(
                'Validacao pre-execucao falhou: ' + '; '.join(validation.errors)
            )

        exec_logger.info('setup', 'Validacao pre-execucao aprovada')

        # -----------------------------------------------------------------
        # 4.6. Calcula max_steps dinamico baseado na complexidade
        # -----------------------------------------------------------------
        exec_params_dict = dict(job_execution_params or {})
        calculated_max_steps = _calculate_max_steps(
            prompt=job_agent_prompt,
            credentials=credentials,
            exec_params=exec_params_dict,
        )
        exec_logger.info('setup', f'max_steps calculado: {calculated_max_steps}')

        # -----------------------------------------------------------------
        # 5. FASE: Browser — Inicializa e executa o BrowserAgent
        # Nivel de erro: FATAL se browser nao iniciar
        # -----------------------------------------------------------------
        exec_logger.info('browser', 'Iniciando agente de navegacao...')

        screenshots: list[bytes] = []
        try:
            from app.modules.agents.browser_agent import BrowserAgent

            browser_agent = BrowserAgent(
                base_url=project_base_url,
                credentials=credentials,
                headless=True,
                timeout=llm_config.get('timeout', 120),
            )

            # Monta os parametros de execucao, incluindo config do LLM
            exec_params = dict(job_execution_params or {})
            exec_params['max_steps'] = calculated_max_steps
            if llm_config.get('api_key'):
                exec_params['llm_config'] = {
                    'provider': llm_config.get('provider'),
                    'model': llm_config.get('model'),
                    'api_key': llm_config.get('api_key'),
                    'temperature': llm_config.get('temperature', 0.7),
                }

            # Progresso: 20% — browser iniciado
            _update_progress(execution_id, 20, db)

            # Executa o agente (async -> sync bridge)
            prompt = job_agent_prompt
            browser_result = _run_async(browser_agent.run(
                prompt=prompt,
                execution_params=exec_params,
            ))

            # Adiciona logs do browser ao exec_logger
            for log_line in browser_result.logs:
                exec_logger.info('browser', log_line)

            if not browser_result.success:
                # Browser rodou mas com erros — CRITICAL, nao FATAL
                # Ainda pode ter capturado screenshots parcialmente
                exec_logger.error(
                    'browser',
                    f'Agente de navegacao finalizou com erros: {browser_result.error_message}',
                    {'error_message': browser_result.error_message},
                )
                logger.warning(
                    'BrowserAgent finalizou com erros para job %s: %s',
                    job_id, browser_result.error_message,
                )
            else:
                exec_logger.info(
                    'browser',
                    f'Agente de navegacao finalizado com sucesso. '
                    f'Screenshots capturados: {len(browser_result.screenshots)}',
                )

            screenshots = browser_result.screenshots

            # Progresso: 40% — navegacao concluida
            _update_progress(execution_id, 40, db)

        except FatalExecutionError:
            raise
        except Exception as e:
            # Browser nao iniciou ou falhou catastroficamente — FATAL
            tb = traceback.format_exc()
            exec_logger.fatal(
                'browser',
                f'Falha fatal ao iniciar/executar agente de navegacao: {str(e)}',
                {'traceback': tb},
            )
            logger.exception('BrowserAgent falhou fatalmente para job %s', job_id)
            raise FatalExecutionError(
                f'Agente de navegacao falhou fatalmente: {str(e)}'
            ) from e

        # -----------------------------------------------------------------
        # 6. FASE: Screenshots — Salva no MinIO
        # Nivel de erro: WARNING (se falhar, PDF e gerado sem screenshots)
        # -----------------------------------------------------------------
        from app.shared.storage import StorageClient

        storage_client = StorageClient()
        screenshots_path: str | None = None

        if screenshots:
            try:
                exec_logger.info(
                    'screenshots',
                    f'Salvando {len(screenshots)} screenshots no storage...',
                )

                from app.modules.agents.screenshot_manager import ScreenshotManager

                screenshot_manager = ScreenshotManager(storage_client)

                saved_paths = screenshot_manager.save_screenshots(
                    screenshots=screenshots,
                    execution_id=str(execution_id),
                )

                screenshots_path = f'screenshots/{execution_id}/'
                exec_logger.info(
                    'screenshots',
                    f'Screenshots salvos: {len(saved_paths)} arquivos',
                    {'saved_count': len(saved_paths), 'path': screenshots_path},
                )

                # Atualiza a Execution com o caminho dos screenshots
                execution_repo.update_status(
                    execution_id=execution_id,
                    status='running',
                    screenshots_path=screenshots_path,
                    logs=exec_logger.to_json(),
                )
            except Exception as e:
                # WARNING: falha ao salvar screenshots; continua sem eles
                tb = traceback.format_exc()
                exec_logger.warning(
                    'screenshots',
                    f'Falha ao salvar screenshots no storage: {str(e)}',
                    {'traceback': tb},
                )
                logger.warning(
                    'Falha ao salvar screenshots para job %s: %s', job_id, str(e),
                )
        else:
            exec_logger.info('screenshots', 'Nenhum screenshot capturado pelo agente')

        # Progresso: 60% — screenshots salvos
        _update_progress(execution_id, 60, db)

        # -----------------------------------------------------------------
        # 7. FASE: Analise LLM — VisionAnalyzer
        # Nivel de erro: WARNING (se falhar, PDF e gerado sem analise)
        # -----------------------------------------------------------------
        extracted_data: dict | None = None
        analysis_text: str = ''

        if screenshots and llm_config.get('api_key'):
            try:
                # Selecao inteligente via ScreenshotClassifier (9.2.3)
                from app.modules.agents.screenshot_classifier import ScreenshotClassifier

                classifier = ScreenshotClassifier()
                classified = classifier.classify_and_select(
                    screenshots, max_screenshots=len(screenshots), logs=[],
                )
                analysis_classified = classifier.select_for_analysis(
                    classified, max_analysis=3,
                )
                analysis_screenshots = [c.image_bytes for c in analysis_classified]

                exec_logger.info(
                    'analysis',
                    f'Iniciando analise visual com LLM '
                    f'({len(analysis_screenshots)} de {len(screenshots)} screenshots, '
                    f'selecionados por relevancia)...',
                )

                from app.modules.agents.vision_analyzer import VisionAnalyzer

                analyzer = VisionAnalyzer.from_llm_config(llm_config)

                analysis_metadata = {
                    'project_name': project_name,
                    'job_name': job_name,
                    'base_url': project_base_url,
                    'execution_id': str(execution_id),
                }

                analysis_result = analyzer.analyze(
                    screenshots=analysis_screenshots,
                    prompt=prompt,
                    metadata=analysis_metadata,
                )

                analysis_text = analysis_result.text
                extracted_data = analysis_result.extracted_data

                exec_logger.info(
                    'analysis',
                    f'Analise visual concluida. Tokens usados: {analysis_result.tokens_used}',
                    {
                        'tokens_used': analysis_result.tokens_used,
                        'has_extracted_data': extracted_data is not None,
                    },
                )
                if extracted_data:
                    exec_logger.info(
                        'analysis',
                        f'Dados extraidos: {json.dumps(extracted_data, ensure_ascii=False)[:200]}',
                    )
                else:
                    exec_logger.info('analysis', 'Nenhum dado estruturado extraido')

            except Exception as e:
                # WARNING: LLM falhou; continua sem analise
                tb = traceback.format_exc()
                exec_logger.warning(
                    'analysis',
                    f'Falha na analise visual (LLM): {str(e)}',
                    {'traceback': tb, 'error_type': type(e).__name__},
                )
                logger.warning('VisionAnalyzer falhou para job %s: %s', job_id, str(e))
        elif not llm_config.get('api_key'):
            exec_logger.info('analysis', 'Analise visual ignorada: API key do LLM nao configurada')
        else:
            exec_logger.info('analysis', 'Analise visual ignorada: nenhum screenshot disponivel')

        # Progresso: 75% — analise concluida
        _update_progress(execution_id, 75, db)

        # -----------------------------------------------------------------
        # 8. FASE: PDF — Gera relatorio com PDFGenerator
        # Nivel de erro: WARNING (se falhar, execucao e success sem PDF)
        # -----------------------------------------------------------------
        pdf_path: str | None = None

        if screenshots:
            try:
                exec_logger.info('pdf', 'Gerando relatorio PDF...')

                from app.modules.agents.pdf_generator import PDFGenerator
                from app.modules.agents.llm_provider import AnalysisResult

                # Cria AnalysisResult para o PDFGenerator
                pdf_analysis = AnalysisResult(
                    text=analysis_text or 'Analise visual nao disponivel.',
                    extracted_data=extracted_data,
                    tokens_used=0,
                )

                pdf_metadata = {
                    'project_name': project_name,
                    'job_name': job_name,
                    'execution_id': str(execution_id),
                    'base_url': project_base_url,
                    'started_at': started_at,
                }

                generator = PDFGenerator()
                pdf_bytes = generator.generate(
                    screenshots=screenshots,
                    analysis=pdf_analysis,
                    metadata=pdf_metadata,
                )

                exec_logger.info(
                    'pdf',
                    f'PDF gerado com sucesso ({len(pdf_bytes)} bytes)',
                    {'size_bytes': len(pdf_bytes)},
                )

                # Salva no MinIO (reutiliza storage_client ja inicializado)
                pdf_path = PDFGenerator.save_to_storage(
                    pdf_bytes=pdf_bytes,
                    execution_id=str(execution_id),
                    storage_client=storage_client,
                )

                exec_logger.info(
                    'pdf',
                    f'PDF salvo no storage: {pdf_path}',
                    {'path': pdf_path},
                )

            except Exception as e:
                # WARNING: PDF falhou; execucao ainda e success
                tb = traceback.format_exc()
                exec_logger.warning(
                    'pdf',
                    f'Falha ao gerar/salvar PDF: {str(e)}',
                    {'traceback': tb},
                )
                logger.warning('PDFGenerator falhou para job %s: %s', job_id, str(e))
        else:
            exec_logger.info('pdf', 'Geracao de PDF ignorada: nenhum screenshot disponivel')

        # Progresso: 90% — PDF gerado
        _update_progress(execution_id, 90, db)

        # -----------------------------------------------------------------
        # 9. FASE: Delivery — Entrega via canais configurados
        # Nivel de erro: INFO (delivery e best-effort; execucao e success)
        # -----------------------------------------------------------------
        if not is_dry_run:
            # Busca configuracoes de entrega ativas do job
            active_delivery_configs = delivery_repo.get_active_configs_by_job(job_uuid)

            if active_delivery_configs:
                exec_logger.info(
                    'delivery',
                    f'Iniciando entrega para {len(active_delivery_configs)} canal(is)...',
                )

                try:
                    execution_data = {
                        'project_name': project_name,
                        'job_name': job_name,
                        'execution_id': str(execution_id),
                        'base_url': project_base_url,
                        'started_at': str(started_at),
                        'analysis_text': analysis_text[:500] if analysis_text else '',
                    }

                    delivery_logs = delivery_service.deliver(
                        execution_id=execution_id,
                        delivery_configs=active_delivery_configs,
                        pdf_path=pdf_path,
                        execution_data=execution_data,
                    )

                    sent_count = sum(1 for dl in delivery_logs if dl.status == 'sent')
                    failed_count = sum(1 for dl in delivery_logs if dl.status == 'failed')

                    if failed_count > 0:
                        exec_logger.warning(
                            'delivery',
                            f'Entrega parcial: {sent_count} enviado(s), {failed_count} falha(s)',
                            {'sent': sent_count, 'failed': failed_count},
                        )
                    else:
                        exec_logger.info(
                            'delivery',
                            f'Entrega concluida: {sent_count} enviado(s)',
                            {'sent': sent_count},
                        )

                except Exception as e:
                    # INFO: delivery falhou, mas execucao e success
                    tb = traceback.format_exc()
                    exec_logger.warning(
                        'delivery',
                        f'Falha na entrega: {str(e)}',
                        {'traceback': tb},
                    )
                    logger.warning('DeliveryService falhou para job %s: %s', job_id, str(e))
            else:
                exec_logger.info('delivery', 'Nenhuma configuracao de entrega ativa para este job')
        else:
            exec_logger.info('delivery', 'Entrega ignorada (dry run)')

        # -----------------------------------------------------------------
        # 10. Finaliza: Atualiza Execution para success
        # -----------------------------------------------------------------
        finished_at = utc_now()
        duration_seconds = int((finished_at - started_at).total_seconds())

        # Determina status final: sempre success se chegou aqui
        # (erros FATAL interrompem o fluxo antes deste ponto)
        final_status = 'success'
        if exec_logger.has_warnings():
            exec_logger.info(
                'finalize',
                f'Execucao concluida com avisos em {duration_seconds}s',
            )
        else:
            exec_logger.info(
                'finalize',
                f'Execucao concluida com sucesso em {duration_seconds}s',
            )

        # Progresso: 100% — concluido
        _update_progress(execution_id, 100, db)

        execution_repo.update_status(
            execution_id=execution_id,
            status=final_status,
            logs=exec_logger.to_json(),
            extracted_data=extracted_data,
            screenshots_path=screenshots_path,
            pdf_path=pdf_path,
            finished_at=finished_at,
            duration_seconds=duration_seconds,
        )

        logger.info(
            'Job %s executado com sucesso (execution_id=%s, duracao=%ds)',
            job_id, str(execution_id), duration_seconds,
        )

        return {
            'success': True,
            'execution_id': str(execution_id),
            'job_id': job_id,
            'duration_seconds': duration_seconds,
            'screenshots_count': len(screenshots) if screenshots else 0,
            'has_extracted_data': extracted_data is not None,
            'has_pdf': pdf_path is not None,
            'is_dry_run': is_dry_run,
            'has_warnings': exec_logger.has_warnings(),
        }

    except self.MaxRetriesExceededError:
        # Retries esgotados para o semaforo
        logger.error(
            'Job %s: maximo de retries esgotado (semaforo cheio). Abortando.',
            job_id,
        )
        return {
            'success': False,
            'job_id': job_id,
            'error': 'Maximo de retries esgotado — semaforo de execucoes permanece cheio.',
        }

    except FatalExecutionError as fatal_err:
        # Erro FATAL: execucao deve ser marcada como failed
        error_msg = str(fatal_err)
        logger.error('Erro FATAL na execucao do job %s: %s', job_id, error_msg)

        if execution_id:
            try:
                finished_at = utc_now()
                duration_seconds = (
                    int((finished_at - started_at).total_seconds())
                    if started_at
                    else None
                )

                exec_logger.fatal('finalize', f'Execucao encerrada por erro fatal: {error_msg}')

                execution_repo.update_status(
                    execution_id=execution_id,
                    status='failed',
                    logs=exec_logger.to_json(),
                    finished_at=finished_at,
                    duration_seconds=duration_seconds,
                )
                logger.info(
                    'Execution %s atualizada para failed (FATAL)', str(execution_id),
                )

                # Notificacao de falha (11.3.4)
                send_failure_notification(
                    job_id=job_uuid,
                    job_name=job_name,
                    execution_id=execution_id,
                    error_message=error_msg,
                    notify_on_failure=notify_on_failure,
                )

            except Exception as update_err:
                logger.error(
                    'Falha ao atualizar Execution %s para failed: %s',
                    str(execution_id), str(update_err),
                )

        return {
            'success': False,
            'execution_id': str(execution_id) if execution_id else None,
            'job_id': job_id,
            'error': error_msg,
            'error_level': 'FATAL',
        }

    except Exception as e:
        # Erro inesperado: atualiza Execution para failed
        error_msg = f'Erro inesperado na execucao do job {job_id}: {str(e)}'
        logger.exception(error_msg)

        if execution_id:
            try:
                finished_at = utc_now()
                duration_seconds = (
                    int((finished_at - started_at).total_seconds())
                    if started_at
                    else None
                )

                # Preserva logs coletados ate o ponto da falha
                exec_logger.fatal('finalize', f'Erro inesperado: {str(e)}')

                execution_repo.update_status(
                    execution_id=execution_id,
                    status='failed',
                    logs=exec_logger.to_json(),
                    finished_at=finished_at,
                    duration_seconds=duration_seconds,
                )
                logger.info(
                    'Execution %s atualizada para failed', str(execution_id),
                )

                # Notificacao de falha (11.3.4)
                send_failure_notification(
                    job_id=job_uuid,
                    job_name=job_name,
                    execution_id=execution_id,
                    error_message=str(e),
                    notify_on_failure=notify_on_failure,
                )

            except Exception as update_err:
                logger.error(
                    'Falha ao atualizar Execution %s para failed: %s',
                    str(execution_id), str(update_err),
                )

        return {
            'success': False,
            'execution_id': str(execution_id) if execution_id else None,
            'job_id': job_id,
            'error': str(e),
        }

    finally:
        # Para o heartbeat thread
        if heartbeat:
            heartbeat.stop()

        # Libera o lock distribuido (com verificacao de ownership)
        if lock_acquired:
            released = _release_lock(redis_client, job_id, lock_token)
            if released:
                logger.debug('Lock liberado para job %s', job_id)
            else:
                logger.warning(
                    'Lock para job %s nao pode ser liberado '
                    '(expirou ou ownership diferente)', job_id,
                )

        # Libera o semaforo global
        if semaphore_acquired:
            _release_semaphore(redis_client)
            logger.debug('Semaforo liberado para job %s', job_id)

        db.close()
        redis_client.close()


# ---------------------------------------------------------------------------
# Helper: Atualiza heartbeat diretamente (usado para o primeiro heartbeat)
# ---------------------------------------------------------------------------

def _update_heartbeat_directly(execution_id: uuid.UUID) -> None:
    """
    Atualiza o last_heartbeat diretamente no banco usando sessao propria.

    Args:
        execution_id: ID da execucao para atualizar heartbeat.
    """
    db = SessionLocal()
    try:
        from app.modules.executions.models import Execution
        from sqlalchemy import select

        now = utc_now()
        stmt = select(Execution).where(Execution.id == execution_id)
        execution = db.execute(stmt).scalar_one_or_none()
        if execution:
            execution.last_heartbeat = now
            db.commit()
    except Exception as e:
        logger.warning(
            'Erro ao definir primeiro heartbeat da execution %s: %s',
            str(execution_id), str(e),
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Task periodica: check_and_dispatch_jobs
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, name='app.modules.jobs.tasks.check_and_dispatch_jobs')
def check_and_dispatch_jobs(self) -> dict:
    """
    Task periodica que verifica jobs ativos e dispara execucoes no horario correto.

    Roda a cada minuto via Celery Beat. Para cada job ativo com cron configurado,
    verifica se a execucao deveria ter sido disparada no ultimo minuto.
    Se sim, enfileira execute_job para aquele job.

    Inclui verificacao de execucao ativa: antes de despachar, consulta se
    existe Execution com status='running' para o mesmo job_id. Se existir
    ha menos de 30 minutos, pula o despacho. Se existir ha mais de 30 minutos,
    considera como orfa e permite novo despacho.

    Returns:
        Dicionario com quantidade de jobs disparados.
    """
    db = SessionLocal()
    dispatched_count = 0
    skipped_active = 0

    try:
        # Importa todos os modelos para garantir que o SQLAlchemy resolva os relacionamentos
        from app.modules.jobs.models import Job  # noqa: F401
        from app.modules.projects.models import Project  # noqa: F401
        from app.modules.executions.models import Execution  # noqa: F401
        from app.modules.delivery.models import DeliveryConfig, DeliveryLog  # noqa: F401
        from app.modules.jobs.repository import JobRepository
        from sqlalchemy import select as sa_select

        job_repo = JobRepository(db)
        active_jobs = job_repo.get_active_jobs()

        now = utc_now()
        # Janela de verificacao: ultimo minuto (60 segundos)
        window_start = now - timedelta(seconds=60)
        # Threshold para considerar execucao como orfa
        orphan_threshold = now - timedelta(minutes=_STALE_EXECUTION_THRESHOLD_MINUTES)

        logger.debug(
            'Verificando %d jobs ativos para agendamento (janela: %s - %s)',
            len(active_jobs), window_start.isoformat(), now.isoformat(),
        )

        for job in active_jobs:
            try:
                if not job.cron_expression:
                    continue

                # Verifica se o projeto esta ativo
                if not job.project or not job.project.is_active:
                    continue

                # Usa croniter para verificar se havia uma execucao agendada
                # dentro da janela de 1 minuto
                cron = croniter(job.cron_expression, window_start)
                next_time = cron.get_next(type(now))

                if next_time <= now:
                    # -------------------------------------------------------
                    # 8.1.2: Verificacao de execucao ativa
                    # -------------------------------------------------------
                    stmt = sa_select(Execution).where(
                        Execution.job_id == job.id,
                        Execution.status == 'running',
                    ).order_by(Execution.started_at.desc()).limit(1)

                    running_execution = db.execute(stmt).scalar_one_or_none()

                    if running_execution:
                        # Verifica se a execucao esta rodando ha muito tempo (orfa)
                        if (
                            running_execution.started_at
                            and running_execution.started_at > orphan_threshold
                        ):
                            # Execucao ativa recente: pula despacho
                            logger.info(
                                'Job %s (%s) ja possui execucao ativa recente '
                                '(execution_id=%s, started_at=%s). Pulando despacho.',
                                str(job.id), job.name,
                                str(running_execution.id),
                                running_execution.started_at.isoformat(),
                            )
                            skipped_active += 1
                            continue
                        else:
                            # Execucao orfa (ha mais de 30 min): permite novo despacho
                            logger.warning(
                                'Job %s (%s) possui execucao orfa '
                                '(execution_id=%s, started_at=%s). '
                                'Permitindo novo despacho.',
                                str(job.id), job.name,
                                str(running_execution.id),
                                (
                                    running_execution.started_at.isoformat()
                                    if running_execution.started_at
                                    else 'N/A'
                                ),
                            )

                    logger.info(
                        'Disparando execucao para job %s (%s) - cron: %s, '
                        'horario agendado: %s',
                        str(job.id), job.name, job.cron_expression,
                        next_time.isoformat(),
                    )

                    execute_job.delay(str(job.id), False)
                    dispatched_count += 1

            except (ValueError, KeyError) as cron_err:
                logger.warning(
                    'Expressao cron invalida para job %s (%s): %s - erro: %s',
                    str(job.id), job.name, job.cron_expression, str(cron_err),
                )
            except Exception as job_err:
                logger.error(
                    'Erro ao verificar agendamento do job %s: %s',
                    str(job.id), str(job_err),
                )

        if dispatched_count > 0 or skipped_active > 0:
            logger.info(
                'check_and_dispatch_jobs: %d job(s) disparado(s), '
                '%d job(s) pulado(s) (execucao ativa)',
                dispatched_count, skipped_active,
            )

        return {
            'success': True,
            'active_jobs_checked': len(active_jobs),
            'dispatched': dispatched_count,
            'skipped_active': skipped_active,
            'checked_at': now.isoformat(),
        }

    except Exception as e:
        logger.exception('Erro em check_and_dispatch_jobs: %s', str(e))
        return {
            'success': False,
            'error': str(e),
        }

    finally:
        db.close()


# ---------------------------------------------------------------------------
# Task periodica: cleanup_stale_executions
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, name='app.modules.jobs.tasks.cleanup_stale_executions')
def cleanup_stale_executions(self) -> dict:
    """
    Task periodica que recupera execucoes orfas (stale execution recovery).

    Roda a cada 5 minutos via Celery Beat. Busca execucoes com status='running'
    que nao tem heartbeat recente (ou que estao rodando ha mais de 30 min
    sem heartbeat). Atualiza para status='failed' com mensagem descritiva
    e libera o lock Redis correspondente.

    Returns:
        Dicionario com quantidade de execucoes recuperadas.
    """
    db = SessionLocal()
    redis_client = _get_redis_client()
    cleaned_count = 0

    try:
        from app.modules.executions.models import Execution
        from app.modules.jobs.models import Job  # noqa: F401
        from sqlalchemy import select as sa_select

        now = utc_now()
        threshold = now - timedelta(minutes=_STALE_EXECUTION_THRESHOLD_MINUTES)

        # Busca execucoes running que estao potencialmente orfas:
        # - started_at ha mais de 30 min E (sem heartbeat OU heartbeat ha mais de 30 min)
        stmt = sa_select(Execution).where(
            Execution.status == 'running',
            Execution.started_at <= threshold,
        )

        stale_executions = list(db.execute(stmt).scalars().all())

        for execution in stale_executions:
            # Verifica heartbeat: se tem heartbeat recente, nao e orfa
            if execution.last_heartbeat and execution.last_heartbeat > threshold:
                logger.debug(
                    'Execution %s tem heartbeat recente (%s). Nao e orfa.',
                    str(execution.id),
                    execution.last_heartbeat.isoformat(),
                )
                continue

            # Execucao orfa confirmada: atualiza para failed
            logger.warning(
                'Execution %s marcada como failed (stale recovery). '
                'Job: %s, started_at: %s, last_heartbeat: %s',
                str(execution.id),
                str(execution.job_id),
                (
                    execution.started_at.isoformat()
                    if execution.started_at
                    else 'N/A'
                ),
                (
                    execution.last_heartbeat.isoformat()
                    if execution.last_heartbeat
                    else 'N/A'
                ),
            )

            finished_at = now
            duration_seconds = (
                int((finished_at - execution.started_at).total_seconds())
                if execution.started_at
                else None
            )

            # Preserva logs existentes e adiciona mensagem de recovery
            existing_logs = execution.logs or ''
            if existing_logs:
                existing_logs += '\n'
            existing_logs += (
                'ERRO: Execucao abandonada — timeout global excedido '
                f'(threshold: {_STALE_EXECUTION_THRESHOLD_MINUTES} min). '
                'Marcada como failed pelo cleanup automatico.'
            )

            execution.status = 'failed'
            execution.logs = existing_logs
            execution.finished_at = finished_at
            if duration_seconds is not None:
                execution.duration_seconds = duration_seconds

            # Libera lock Redis correspondente
            lock_released = _force_release_lock(
                redis_client, str(execution.job_id),
            )
            if lock_released:
                logger.info(
                    'Lock Redis liberado para job %s (stale recovery)',
                    str(execution.job_id),
                )

            cleaned_count += 1

        if stale_executions:
            db.commit()

        if cleaned_count > 0:
            logger.info(
                'cleanup_stale_executions: %d execucao(oes) recuperada(s)',
                cleaned_count,
            )

        return {
            'success': True,
            'stale_found': len(stale_executions),
            'cleaned': cleaned_count,
            'checked_at': now.isoformat(),
        }

    except Exception as e:
        logger.exception('Erro em cleanup_stale_executions: %s', str(e))
        return {
            'success': False,
            'error': str(e),
        }

    finally:
        db.close()
        redis_client.close()


# ---------------------------------------------------------------------------
# Funcao auxiliar: sync bridge para funcoes async
# ---------------------------------------------------------------------------

def _run_async(coro) -> 'object':
    """
    Executa uma coroutine de forma sincrona.

    Celery tasks sao sincronas por padrao. Esta funcao cria um event loop
    temporario para executar coroutines async (como BrowserAgent.run).

    Args:
        coro: Coroutine a ser executada.

    Returns:
        Resultado da coroutine.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Se ja ha um loop rodando, cria um novo em uma thread separada
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        # Nenhum event loop disponivel, cria um novo
        return asyncio.run(coro)
