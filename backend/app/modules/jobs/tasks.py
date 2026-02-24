import asyncio
import json
import logging
import uuid

from croniter import croniter

from app.celery_app import celery_app
from app.database import SessionLocal
from app.shared.utils import utc_now

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Task principal: execute_job
# ---------------------------------------------------------------------------

@celery_app.task(bind=True, name='app.modules.jobs.tasks.execute_job')
def execute_job(self, job_id: str, is_dry_run: bool = False) -> dict:
    """
    Task Celery que executa o fluxo completo de um job.

    Fluxo:
    1. Busca o Job com projeto e delivery configs
    2. Cria registro de Execution (status=pending)
    3. Atualiza para running, inicia BrowserAgent
    4. Salva screenshots no MinIO
    5. Analisa com VisionAnalyzer (LLM)
    6. Gera PDF com PDFGenerator
    7. Salva PDF no MinIO
    8. Entrega via DeliveryService (exceto dry_run)
    9. Atualiza Execution para success ou failed

    Args:
        self: Instancia da task (bind=True).
        job_id: ID do job a ser executado (string UUID).
        is_dry_run: Se True, pula a etapa de entrega.

    Returns:
        Dicionario com resultado da execucao.
    """
    job_uuid = uuid.UUID(job_id)
    execution_id: uuid.UUID | None = None
    started_at = None
    all_logs: list[str] = []
    db = SessionLocal()

    try:
        logger.info(
            'Iniciando execucao do job %s (dry_run=%s, task_id=%s)',
            job_id, is_dry_run, self.request.id,
        )

        # -----------------------------------------------------------------
        # 1. Busca o Job com projeto e delivery configs
        # -----------------------------------------------------------------
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

        logger.info(
            'Job encontrado: %s (projeto: %s, URL: %s)',
            job.name, project.name, project.base_url,
        )

        # -----------------------------------------------------------------
        # 2. Cria registro de Execution (status=pending)
        # -----------------------------------------------------------------
        execution = execution_repo.create({
            'job_id': job_uuid,
            'status': 'pending',
            'is_dry_run': is_dry_run,
        })
        execution_id = execution.id
        logger.info(
            'Execution criada: %s (status=pending)', str(execution_id),
        )

        # -----------------------------------------------------------------
        # 3. Atualiza para running e registra started_at
        # -----------------------------------------------------------------
        started_at = utc_now()
        execution_repo.update_status(
            execution_id=execution_id,
            status='running',
            started_at=started_at,
        )
        logger.info('Execution %s atualizada para running', str(execution_id))

        all_logs.append(f'Iniciando execucao do job "{job.name}"')
        all_logs.append(f'Projeto: {project.name} | URL: {project.base_url}')
        all_logs.append(f'Dry run: {is_dry_run}')
        all_logs.append(f'Task ID: {self.request.id}')

        # -----------------------------------------------------------------
        # 4. Obtem credenciais e configuracao LLM do projeto
        # -----------------------------------------------------------------
        credentials: dict | None = None
        try:
            credentials = project_service.get_decrypted_credentials(project.id)
            if credentials:
                all_logs.append('Credenciais do projeto carregadas com sucesso')
            else:
                all_logs.append('Projeto sem credenciais configuradas')
        except Exception as e:
            all_logs.append(f'Aviso: nao foi possivel carregar credenciais: {str(e)}')
            logger.warning('Falha ao carregar credenciais do projeto %s: %s', project.id, str(e))

        llm_config: dict = {}
        try:
            llm_config = project_service.get_llm_config(project.id)
            all_logs.append(
                f'LLM configurado: {llm_config.get("provider")} / {llm_config.get("model")}'
            )
        except Exception as e:
            all_logs.append(f'Aviso: nao foi possivel carregar config LLM: {str(e)}')
            logger.warning('Falha ao carregar config LLM do projeto %s: %s', project.id, str(e))

        # -----------------------------------------------------------------
        # 5. Inicializa e executa o BrowserAgent
        # -----------------------------------------------------------------
        all_logs.append('Iniciando agente de navegacao...')

        from app.modules.agents.browser_agent import BrowserAgent

        browser_agent = BrowserAgent(
            base_url=project.base_url,
            credentials=credentials,
            headless=True,
            timeout=llm_config.get('timeout', 120),
        )

        # Monta os parametros de execucao, incluindo config do LLM
        # para que o browser-use possa usar o agente inteligente
        exec_params = dict(job.execution_params or {})
        if llm_config.get('api_key'):
            exec_params['llm_config'] = {
                'provider': llm_config.get('provider'),
                'model': llm_config.get('model'),
                'api_key': llm_config.get('api_key'),
                'temperature': llm_config.get('temperature', 0.7),
            }

        # Executa o agente (async -> sync bridge)
        prompt = job.agent_prompt
        browser_result = _run_async(browser_agent.run(
            prompt=prompt,
            execution_params=exec_params,
        ))

        all_logs.extend(browser_result.logs)

        if not browser_result.success:
            all_logs.append(
                f'Agente de navegacao finalizou com erros: {browser_result.error_message}'
            )
            logger.warning(
                'BrowserAgent finalizou com erros para job %s: %s',
                job_id, browser_result.error_message,
            )
        else:
            all_logs.append(
                f'Agente de navegacao finalizado com sucesso. '
                f'Screenshots capturados: {len(browser_result.screenshots)}'
            )

        screenshots = browser_result.screenshots

        # -----------------------------------------------------------------
        # 6. Salva screenshots no MinIO
        # -----------------------------------------------------------------
        from app.shared.storage import StorageClient

        storage_client = StorageClient()
        screenshots_path: str | None = None

        if screenshots:
            all_logs.append(f'Salvando {len(screenshots)} screenshots no storage...')

            from app.modules.agents.screenshot_manager import ScreenshotManager

            screenshot_manager = ScreenshotManager(storage_client)

            saved_paths = screenshot_manager.save_screenshots(
                screenshots=screenshots,
                execution_id=str(execution_id),
            )

            screenshots_path = f'screenshots/{execution_id}/'
            all_logs.append(f'Screenshots salvos: {len(saved_paths)} arquivos')

            # Atualiza a Execution com o caminho dos screenshots
            execution_repo.update_status(
                execution_id=execution_id,
                status='running',
                screenshots_path=screenshots_path,
                logs='\n'.join(all_logs),
            )
        else:
            all_logs.append('Nenhum screenshot capturado pelo agente')

        # -----------------------------------------------------------------
        # 7. Analisa screenshots com VisionAnalyzer (LLM)
        # -----------------------------------------------------------------
        extracted_data: dict | None = None
        analysis_text: str = ''

        if screenshots and llm_config.get('api_key'):
            all_logs.append('Iniciando analise visual com LLM...')

            from app.modules.agents.vision_analyzer import VisionAnalyzer

            try:
                analyzer = VisionAnalyzer.from_llm_config(llm_config)

                analysis_metadata = {
                    'project_name': project.name,
                    'job_name': job.name,
                    'base_url': project.base_url,
                    'execution_id': str(execution_id),
                }

                analysis_result = analyzer.analyze(
                    screenshots=screenshots,
                    prompt=prompt,
                    metadata=analysis_metadata,
                )

                analysis_text = analysis_result.text
                extracted_data = analysis_result.extracted_data

                all_logs.append(
                    f'Analise visual concluida. Tokens usados: {analysis_result.tokens_used}'
                )
                if extracted_data:
                    all_logs.append(
                        f'Dados extraidos: {json.dumps(extracted_data, ensure_ascii=False)[:200]}'
                    )
                else:
                    all_logs.append('Nenhum dado estruturado extraido')

            except Exception as e:
                error_msg = f'Erro na analise visual: {str(e)}'
                all_logs.append(error_msg)
                logger.error('VisionAnalyzer falhou para job %s: %s', job_id, str(e))
        elif not llm_config.get('api_key'):
            all_logs.append('Analise visual ignorada: API key do LLM nao configurada')
        else:
            all_logs.append('Analise visual ignorada: nenhum screenshot disponivel')

        # -----------------------------------------------------------------
        # 8. Gera PDF com PDFGenerator
        # -----------------------------------------------------------------
        pdf_path: str | None = None

        if screenshots:
            all_logs.append('Gerando relatorio PDF...')

            from app.modules.agents.pdf_generator import PDFGenerator
            from app.modules.agents.llm_provider import AnalysisResult

            try:
                # Cria AnalysisResult para o PDFGenerator
                pdf_analysis = AnalysisResult(
                    text=analysis_text or 'Analise visual nao disponivel.',
                    extracted_data=extracted_data,
                    tokens_used=0,
                )

                pdf_metadata = {
                    'project_name': project.name,
                    'job_name': job.name,
                    'execution_id': str(execution_id),
                    'base_url': project.base_url,
                    'started_at': started_at,
                }

                generator = PDFGenerator()
                pdf_bytes = generator.generate(
                    screenshots=screenshots,
                    analysis=pdf_analysis,
                    metadata=pdf_metadata,
                )

                all_logs.append(f'PDF gerado com sucesso ({len(pdf_bytes)} bytes)')

                # Salva no MinIO (reutiliza storage_client ja inicializado)
                pdf_path = PDFGenerator.save_to_storage(
                    pdf_bytes=pdf_bytes,
                    execution_id=str(execution_id),
                    storage_client=storage_client,
                )

                all_logs.append(f'PDF salvo no storage: {pdf_path}')

            except Exception as e:
                error_msg = f'Erro ao gerar/salvar PDF: {str(e)}'
                all_logs.append(error_msg)
                logger.error('PDFGenerator falhou para job %s: %s', job_id, str(e))
        else:
            all_logs.append('Geracao de PDF ignorada: nenhum screenshot disponivel')

        # -----------------------------------------------------------------
        # 9. Entrega via DeliveryService (exceto dry_run)
        # -----------------------------------------------------------------
        if not is_dry_run:
            # Busca configuracoes de entrega ativas do job
            active_delivery_configs = delivery_repo.get_active_configs_by_job(job_uuid)

            if active_delivery_configs:
                all_logs.append(
                    f'Iniciando entrega para {len(active_delivery_configs)} canal(is)...'
                )

                try:
                    execution_data = {
                        'project_name': project.name,
                        'job_name': job.name,
                        'execution_id': str(execution_id),
                        'base_url': project.base_url,
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

                    all_logs.append(
                        f'Entrega concluida: {sent_count} enviado(s), {failed_count} falha(s)'
                    )

                except Exception as e:
                    error_msg = f'Erro durante entrega: {str(e)}'
                    all_logs.append(error_msg)
                    logger.error('DeliveryService falhou para job %s: %s', job_id, str(e))
            else:
                all_logs.append('Nenhuma configuracao de entrega ativa para este job')
        else:
            all_logs.append('Entrega ignorada (dry run)')

        # -----------------------------------------------------------------
        # 10. Atualiza Execution para success
        # -----------------------------------------------------------------
        finished_at = utc_now()
        duration_seconds = int((finished_at - started_at).total_seconds())

        all_logs.append(f'Execucao concluida com sucesso em {duration_seconds}s')

        execution_repo.update_status(
            execution_id=execution_id,
            status='success',
            logs='\n'.join(all_logs),
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

                # Tenta preservar logs coletados ate o ponto da falha
                all_logs.append(f'ERRO FATAL: {str(e)}')

                execution_repo.update_status(
                    execution_id=execution_id,
                    status='failed',
                    logs='\n'.join(all_logs),
                    finished_at=finished_at,
                    duration_seconds=duration_seconds,
                )
                logger.info(
                    'Execution %s atualizada para failed', str(execution_id),
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

    Este approach simples dispensa RedBeat ou DatabaseScheduler,
    verificando os crons dinamicamente a cada minuto.

    Returns:
        Dicionario com quantidade de jobs disparados.
    """
    db = SessionLocal()
    dispatched_count = 0

    try:
        from app.modules.jobs.repository import JobRepository
        from datetime import timedelta

        job_repo = JobRepository(db)
        active_jobs = job_repo.get_active_jobs()

        now = utc_now()
        # Janela de verificacao: ultimo minuto (60 segundos)
        window_start = now - timedelta(seconds=60)

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

        if dispatched_count > 0:
            logger.info(
                'check_and_dispatch_jobs: %d job(s) disparado(s)', dispatched_count,
            )

        return {
            'success': True,
            'active_jobs_checked': len(active_jobs),
            'dispatched': dispatched_count,
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
