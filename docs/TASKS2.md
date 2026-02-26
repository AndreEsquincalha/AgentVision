# TASKS2.md — Melhorias Profissionais para o AgentVision

> **Gerado em:** 2026-02-24
> **Objetivo:** Transformar o AgentVision em uma plataforma de automação de nível enterprise, com foco em confiabilidade, segurança, otimização de tokens, inteligência de navegação, controle de execuções e robustez na geração de relatórios.

---

## Sprint 8 — Controle de Execuções e Proteção contra Duplicidade

> **Prioridade:** CRÍTICA
> **Objetivo:** Garantir que jobs nunca executem em duplicidade, que execuções travadas sejam recuperadas, e que haja controle total sobre o ciclo de vida das execuções.

### 8.1 Distributed Lock para Prevenção de Execuções Duplicadas

- [X] **8.1.1** Implementar distributed lock com Redis para `execute_job`

  - Usar Redis `SET key NX EX ttl` (lock atômico com expiração)
  - Chave de lock: `job_lock:{job_id}` — impede 2 execuções do mesmo job ao mesmo tempo
  - TTL do lock = timeout máximo do job + margem de segurança (ex: `max_steps * timeout_per_step + 120s`)
  - Liberar lock no `finally` da task (com verificação de ownership via token UUID)
  - Logar quando lock não é adquirido: `"Job {job_id} já está em execução, pulando"`
- [X] **8.1.2** Adicionar verificação de execução ativa antes de despachar no `check_and_dispatch_jobs`

  - Antes de chamar `execute_job.delay()`, consultar se existe `Execution` com `status='running'` para o mesmo `job_id`
  - Se existir execução running com mais de `N` minutos (threshold configurável), considerar como órfã
  - Logar e pular despacho se já há execução ativa
- [X] **8.1.3** Criar campo `celery_task_id` no model `Execution`

  - Migração Alembic: adicionar coluna `celery_task_id` (String, nullable, indexed)
  - Gravar `self.request.id` do Celery ao criar a Execution
  - Permitir correlação entre task Celery e Execution no banco
- [X] **8.1.4** Criar endpoint `POST /api/executions/{id}/cancel` para cancelamento

  - Revogar task Celery via `celery_app.control.revoke(task_id, terminate=True)`
  - Atualizar status da Execution para `cancelled`
  - Adicionar status `cancelled` ao enum de status (model + schema + frontend)

### 8.2 Recuperação de Execuções Órfãs (Stale Execution Recovery)

- [X] **8.2.1** Criar task periódica `cleanup_stale_executions`

  - Rodar a cada 5 minutos via Celery Beat
  - Buscar execuções com `status='running'` e `started_at` há mais de `MAX_EXECUTION_DURATION` (ex: 30 min)
  - Atualizar para `status='failed'` com mensagem: `"Execução abandonada — timeout global excedido"`
  - Liberar lock Redis correspondente se existir
  - Registrar no log: `"Execution {id} marcada como failed (stale recovery)"`
- [X] **8.2.2** Adicionar campo `last_heartbeat` no model `Execution`

  - Migração Alembic: adicionar coluna `last_heartbeat` (DateTime, nullable)
  - Atualizar heartbeat periodicamente durante a execução (a cada 30s)
  - Task de cleanup usa `last_heartbeat` em vez de `started_at` para identificar execuções realmente travadas
- [X] **8.2.3** Implementar heartbeat na task `execute_job`

  - Criar thread daemon que atualiza `last_heartbeat` no banco a cada 30s
  - Parar thread no finally da task
  - Heartbeat serve como prova de vida — se parar de atualizar, a execução é considerada morta

### 8.3 Controle de Concorrência Global

- [X] **8.3.1** Implementar limite global de execuções simultâneas

  - Usar semáforo Redis: `execution_semaphore` com `max_concurrent_jobs` (configurável em Settings)
  - Antes de executar, fazer `acquire()` no semáforo; no `finally`, fazer `release()`
  - Se semáforo cheio, reenfileirar a task com countdown (retry após N segundos)
  - Default: `max_concurrent_jobs = 3`
- [X] **8.3.2** Adicionar configuração `max_concurrent_jobs` no módulo Settings

  - Nova chave no Settings: `execution.max_concurrent_jobs` (categoria `execution`)
  - Endpoint para consultar e alterar
  - Frontend: campo em Settings para configurar
- [X] **8.3.3** Implementar fila de prioridade para jobs

  - Jobs marcados como `high_priority` entram em fila prioritária
  - Adicionar campo `priority` no model Job (default='normal', enum: 'low', 'normal', 'high')
  - Migração Alembic para nova coluna
  - Celery routing: tasks high_priority vão para queue `priority`, demais para `default`

---

## Sprint 9 — Otimização de Consumo de Tokens LLM

> **Prioridade:** ALTA
> **Objetivo:** Reduzir drasticamente o consumo de tokens sem perder qualidade de análise. Cada token gasto deve ter máximo valor analítico.

### 9.1 Screenshot Intelligence — Captura Seletiva e Inteligente

- [X] **9.1.1** Implementar classificação de screenshots por relevância

  - Criar classe `ScreenshotClassifier` em `agents/screenshot_classifier.py`
  - Critérios de relevância:
    - **Diferença visual**: comparar perceptual hash (pHash) entre screenshots consecutivos
    - **Momento de captura**: screenshots pós-ação (login, submit, navegação) valem mais
    - **Conteúdo detectado**: se contém tabelas, formulários, dados — é relevante
  - Retornar lista ordenada por relevância com score 0.0-1.0
- [X] **9.1.2** Substituir deduplicação por hash por perceptual hashing (pHash)

  - Remover `hash(img)` (não-determinístico, ineficaz) de `browser_agent.py:201-213`
  - Implementar pHash usando `imagehash` ou `Pillow` diretamente:
    ```python
    from PIL import Image
    import hashlib, io
    def perceptual_hash(img_bytes: bytes, threshold: int = 5) -> str:
        img = Image.open(io.BytesIO(img_bytes)).convert('L').resize((8, 8))
        avg = sum(img.getdata()) / 64
        return ''.join('1' if px > avg else '0' for px in img.getdata())
    ```
  - Dois screenshots com distância de Hamming < threshold são considerados duplicados
  - Manter apenas o de melhor resolução entre duplicados
- [X] **9.1.3** Implementar estratégia de captura "momentos-chave" no BrowserAgent

  - Definir eventos de captura obrigatórios: `page_loaded`, `after_login`, `after_action`, `final_state`
  - Definir eventos opcionais: `error_detected`, `data_found`, `navigation_change`
  - Instruir o browser-use agent via prompt a **não** capturar screenshots de cada passo
  - Adicionar ao prompt do agente:
    ```
    NÃO capture screenshots de cada passo. Capture APENAS nos seguintes momentos:
    1. Após carregar a página principal
    2. Após realizar login (se aplicável)
    3. Quando encontrar os dados/informações solicitados
    4. No estado final após completar a tarefa
    ```
- [X] **9.1.4** Limitar número máximo de screenshots por execução

  - Adicionar campo `max_screenshots` no Job `execution_params` (default: 10)
  - Se browser-use gerar mais que `max_screenshots`, selecionar os mais relevantes via `ScreenshotClassifier`
  - Log: `"Screenshots limitados: {original} -> {max_screenshots} (selecionados por relevância)"`

### 9.2 Otimização de Prompts para Economia de Tokens

- [X] **9.2.1** Reduzir e otimizar o `_SYSTEM_PROMPT_TEMPLATE` do VisionAnalyzer

  - Prompt atual é verboso (~500 tokens só de template)
  - Criar versão compacta sem perder instruções:
    - Remover redundâncias e exemplos desnecessários
    - Usar formato de instrução direto (não explicativo)
    - Reduzir template JSON — usar formato mínimo com campos obrigatórios
  - Objetivo: reduzir template de ~500 para ~200 tokens (60% economia)
- [X] **9.2.2** Implementar image resizing antes de enviar ao LLM

  - Redimensionar screenshots para resolução ótima por provider:
    - Anthropic Claude: 1568px no lado maior (limite de ~1.15M pixels)
    - OpenAI GPT-4o: 2048px ou 768px (modo `low`/`high` detail)
    - Google Gemini: 3072px (suporta alta resolução)
  - Comprimir para JPEG quality 85 quando não há texto pequeno
  - Manter PNG apenas se detectar texto fino ou elementos UI críticos
  - Calcular economia: screenshot original ~500KB → comprimido ~80KB = ~84% menos tokens de imagem
- [X] **9.2.3** Implementar seleção inteligente de screenshots para análise

  - Substituir seleção fixa "primeiro, meio, último" por seleção por relevância
  - Usar scores do `ScreenshotClassifier` para enviar apenas os mais informativos
  - Se análise anterior (browser-use extracted_content) já tem dados suficientes, reduzir para 1 screenshot
  - Heurística: se extracted_content >= 500 chars, enviar apenas screenshot final
- [X] **9.2.4** Implementar contagem estimada de tokens antes de enviar ao LLM

  - Criar método `estimate_tokens()` em cada provider:
    - Texto: ~4 chars = 1 token (PT-BR), ~3.5 chars = 1 token (EN)
    - Imagens Anthropic: largura * altura / 750 tokens (aproximação)
    - Imagens OpenAI: tiles de 512x512, cada tile ~170 tokens
    - Imagens Gemini: ~258 tokens por imagem
  - Validar `estimated_tokens < context_limit - max_output_tokens` antes de enviar
  - Se exceder, reduzir resolução ou número de imagens automaticamente
- [X] **9.2.5** Implementar cache de análises (evitar re-análise de mesmos screenshots)

  - Hash SHA-256 dos screenshots + hash do prompt = chave de cache
  - Armazenar resultado no Redis com TTL de 1 hora
  - Se cache hit, retornar resultado cacheado sem chamar LLM
  - Log: `"Cache hit para análise — tokens economizados: {estimated_tokens}"`

### 9.3 Monitoramento e Tracking de Consumo de Tokens

- [X] **9.3.1** Criar tabela `token_usage` para tracking de consumo

  - Migração Alembic: nova tabela `token_usage`
    - `id` (UUID), `execution_id` (FK), `provider` (str), `model` (str)
    - `input_tokens` (int), `output_tokens` (int), `total_tokens` (int)
    - `estimated_cost_usd` (float), `image_count` (int)
    - `created_at` (datetime)
  - Repository e Service para consultas de consumo
- [X] **9.3.2** Registrar uso de tokens em cada chamada LLM

  - Em cada provider, após `analyze_images()`, salvar em `token_usage`
  - Incluir custo estimado por modelo:
    - Claude Sonnet: $3/1M input, $15/1M output
    - GPT-4o: $2.50/1M input, $10/1M output
    - Gemini 2.0 Flash: $0.10/1M input, $0.40/1M output
  - Atualizar campo `tokens_used` na Execution
- [X] **9.3.3** Criar endpoint e dashboard de consumo de tokens

  - `GET /api/dashboard/token-usage` — consumo por provider, período, job
  - Métricas: total de tokens, custo estimado, média por execução, tendência
  - Frontend: cards com consumo diário/semanal/mensal e gráfico de tendência
- [X] **9.3.4** Implementar limites de tokens (budget control)

  - Configuração em Settings: `token_budget.daily_limit`, `token_budget.monthly_limit`
  - Antes de enviar para LLM, verificar se o budget não foi excedido
  - Se excedido: falhar a execução com mensagem clara, não chamar LLM
  - Alertas: notificar quando budget atingir 80% e 100%

---

## Sprint 10 — Inteligência de Navegação e Segurança do Agente

> **Prioridade:** ALTA
> **Objetivo:** Tornar o agente mais assertivo na navegação, com sandbox de segurança para impedir ações não autorizadas e detecção de loops.

### 10.1 Detecção e Prevenção de Loops

- [X] **10.1.1** Implementar detector de loops baseado em URL tracking

  - Criar classe `LoopDetector` em `agents/loop_detector.py`
  - Manter histórico de URLs visitadas com timestamps
  - Detectar padrões de loop:
    - **URL repetida**: mesma URL visitada >= 3 vezes
    - **Ciclo de URLs**: sequência A→B→C→A detectada >= 2 vezes
    - **Progresso estagnado**: nenhuma URL nova nos últimos N steps
  - Retornar `LoopDetection(is_loop=True, type='url_repeat', count=3)`
- [X] **10.1.2** Implementar detector de loops baseado em ação repetida

  - Detectar quando o agente repete a mesma ação (click, type) no mesmo elemento
  - Threshold configurável: `max_repeated_actions = 3`
  - Integrar com os logs do browser-use para monitorar ações
  - Se loop detectado: emitir warning no log e considerar fallback
- [X] **10.1.3** Implementar circuit breaker para o agente

  - Se loop detectado, injetar instrução de correção no prompt do agente:
    ```
    ATENÇÃO: Você está repetindo ações. Pare e analise se a tarefa já foi concluída.
    Se sim, finalize imediatamente. Se não, tente uma abordagem diferente.
    ```
  - Se após correção o loop persistir (2ª detecção), forçar parada do agente
  - Retornar BrowserResult com `success=False, error_message="Loop detectado e agente forçado a parar"`
  - Capturar screenshot final antes de parar
- [X] **10.1.4** Adicionar `max_steps` dinâmico baseado na complexidade da tarefa

  - Jobs simples (apenas captura de screenshot): `max_steps = 5`
  - Jobs com login: `max_steps = 10`
  - Jobs com navegação multi-página: `max_steps = 15`
  - Jobs complexos (extração de dados, formulários): `max_steps = 25`
  - Campo `complexity` no Job (auto-detectado ou manual)

### 10.2 Sandbox de Segurança para o Agente

- [X] **10.2.1** Implementar URL allowlist/blocklist por projeto

  - Adicionar campos no model Project:
    - `allowed_domains` (JSON list) — domínios permitidos para navegação
    - `blocked_urls` (JSON list) — URLs/patterns bloqueadas
  - O agente só pode navegar em domínios presentes no `allowed_domains`
  - Bloquear navegação para URLs externas automaticamente
- [X] **10.2.2** Implementar action sandbox — limitar ações do agente

  - Criar enum `AllowedActions`: `navigate`, `click`, `type`, `screenshot`, `extract`, `scroll`
  - Cada job define quais ações são permitidas (default: todas exceto `download`, `upload`, `execute_js`)
  - Ações perigosas bloqueadas por padrão:
    - `download` — download de arquivos
    - `upload` — upload de arquivos
    - `execute_js` — execução de JavaScript arbitrário
    - `form_submit` com campos de pagamento
  - Bloquear via prompt engineering + validação pós-ação
- [X] **10.2.3** Implementar timeout granular por fase de execução

  - Timeouts separados para cada fase:
    - `login_timeout`: 30s (login deve ser rápido)
    - `navigation_timeout`: 60s por página
    - `extraction_timeout`: 30s para extração de dados
    - `total_timeout`: calculado como soma de fases + margem
  - Se qualquer fase exceder seu timeout, log de warning e fallback para próxima fase
  - Timeout total é hard limit — mata o processo
- [X] **10.2.4** Implementar validação de credenciais antes da execução

  - Antes de iniciar o BrowserAgent, validar:
    - Credenciais existem e não estão vazias
    - API key do LLM é válida (ping rápido no provider)
    - URL base responde (HEAD request com timeout de 5s)
  - Se qualquer validação falhar, abortar execução imediatamente com erro descritivo
  - Evitar gastar recursos (browser, tokens) em execuções fadadas a falhar

### 10.3 Melhoria na Assertividade da Navegação

- [X] **10.3.1** Melhorar o prompt do browser-use agent com instruções mais precisas

  - Refatorar `_build_full_prompt()` para ser mais direto e assertivo:
    ```
    Você é um agente de automação web. Siga EXATAMENTE estas instruções na ordem:
    1. Navegue para {url}
    2. {login_instructions se aplicável}
    3. {prompt_do_usuario}
    4. Capture screenshots APENAS dos resultados encontrados
    5. Finalize imediatamente após completar todas as instruções

    REGRAS:
    - NÃO explore páginas não solicitadas
    - NÃO clique em links não relacionados à tarefa
    - NÃO repita ações já concluídas
    - Se uma ação falhar, tente NO MÁXIMO 2 vezes antes de prosseguir
    ```
- [X] **10.3.2** Implementar fallback inteligente (browser-use → Playwright dirigido)

  - Se browser-use falhar, em vez de Playwright genérico, usar Playwright com instruções extraídas do prompt:
    - Parser de prompt: extrair URLs, ações e dados esperados
    - Mapear ações para Playwright API: `page.goto()`, `page.click()`, `page.fill()`
  - Criar classe `PromptToPlaywright` que converte instruções em scripts Playwright
  - Manter extracted_content do browser-use (se parcial) como contexto para o fallback
- [X] **10.3.3** Adicionar detecção de estado da página antes de ações

  - Antes de cada ação do agente, verificar:
    - Página carregou completamente (`networkidle` ou `domcontentloaded`)
    - Não há overlays/modais bloqueando interação
    - O elemento alvo está visível e interativo
  - Implementar `page.wait_for_load_state('networkidle')` com timeout curto (5s)
  - Se modal/popup detectado, fechar automaticamente antes de prosseguir
- [X] **10.3.4** Implementar retry inteligente com contexto de erro

  - Se uma ação falhar (ex: element not found), não repetir cegamente
  - Analisar o erro e ajustar estratégia:
    - `element not found` → aguardar + tentar seletor alternativo
    - `timeout` → aumentar timeout e tentar novamente
    - `navigation failed` → verificar se URL é acessível
    - `click intercepted` → scroll para elemento + retry
  - Máximo de 2 retries por ação, depois prosseguir com log de warning

---

## Sprint 11 — Robustez na Geração de PDFs e Tratamento de Erros

> **Prioridade:** ALTA
> **Objetivo:** Garantir que PDFs sempre sejam gerados corretamente, com tratamento de todos os cenários de erro e relatórios úteis mesmo em caso de falha parcial.

### 11.1 Geração Resiliente de PDFs

- [X] **11.1.1** Implementar geração de PDF com fallback progressivo

  - Cenário ideal: screenshots + análise LLM + dados extraídos → PDF completo
  - Fallback 1: screenshots + sem análise → PDF com screenshots e metadados
  - Fallback 2: sem screenshots + análise LLM → PDF com texto da análise
  - Fallback 3: erro total → PDF mínimo com logs de execução e status de erro
  - Nunca falhar completamente — sempre gerar algum PDF informativo
- [X] **11.1.2** Adicionar validação de screenshots antes de incluir no PDF

  - Verificar que o bytes é uma imagem válida (magic bytes check)
  - Verificar tamanho mínimo (> 1KB) e máximo (< 10MB)
  - Se imagem corrompida, logar warning e pular (não crashar o PDF inteiro)
  - Redimensionar imagens maiores que 1920x1080 para caber na página
- [X] **11.1.3** Implementar tratamento de conteúdo dinâmico no PDF

  - Truncar textos muito longos com `... [texto truncado, ver log completo]`
  - Escapar caracteres especiais (LaTeX/ReportLab) que podem quebrar o build
  - Tabelas com muitas colunas: auto-ajustar largura ou dividir em múltiplas páginas
  - Lidar com UTF-8 corretamente (acentos, caracteres especiais)
- [X] **11.1.4** Adicionar retry na geração de PDF

  - Se `PDFGenerator.generate()` falhar, tentar novamente com:
    - 1º retry: mesmos parâmetros (pode ser erro transiente)
    - 2º retry: sem imagens (gerar PDF texto-only)
    - 3º retry: PDF mínimo (apenas metadados + error log)
  - Máximo de 3 tentativas com log de cada falha
- [X] **11.1.5** Implementar streaming de PDF para MinIO (evitar OOM)

  - Atualmente: PDF gerado em memória via `BytesIO`, depois upload
  - Melhoria: para PDFs grandes (>10MB), usar arquivo temporário:
    ```python
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=True) as tmp:
        doc = SimpleDocTemplate(tmp.name, ...)
        doc.build(story)
        storage_client.upload_file_from_path(tmp.name, key)
    ```
  - Limite de memória: se `len(pdf_bytes) > 50MB`, abortar e logar erro

### 11.2 Melhorias no Conteúdo do PDF

- [X] **11.2.1** Adicionar seção de sumário executivo no início do PDF

  - Gerado a partir do `extracted_data.summary` do LLM
  - Se análise não disponível, usar extracted_content do browser-use
  - Formato: 2-3 bullet points com as descobertas principais
  - Posicionar logo após a capa, antes dos screenshots
- [X] **11.2.2** Implementar seção de status/resultado visual

  - Badge colorido de status: SUCCESS (verde), PARTIAL (amarelo), FAILED (vermelho)
  - Métricas visuais: duração, screenshots capturados, tokens usados
  - Timeline de execução: hora início → login → navegação → análise → conclusão
- [X] **11.2.3** Melhorar legendas dos screenshots

  - Em vez de "Screenshot 1", "Screenshot 2", usar contexto:
    - "Página inicial - {url}"
    - "Após login - Dashboard"
    - "Resultado da busca - {query}"
  - Extrair contexto do log do browser-use (URLs visitadas, ações realizadas)
  - Timestamp em cada screenshot
- [X] **11.2.4** Adicionar marca d'água e metadados no PDF

  - Marca d'água discreta: "Gerado por AgentVision"
  - Metadados PDF: autor, título, subject, keywords, creation date
  - Número de páginas no rodapé: "Página X de Y"
  - QR Code opcional com link para a execução no frontend

### 11.3 Tratamento de Erros no Pipeline de Execução

- [X] **11.3.1** Implementar error recovery granular na task `execute_job`

  - Cada fase (browser, screenshots, análise, PDF, delivery) deve:
    - Ter seu próprio try/except
    - Logar o erro com stack trace
    - Decidir se a execução deve continuar ou parar
  - Hierarquia de erros:
    - FATAL: browser não inicia, URL inacessível → parar e marcar como failed
    - CRITICAL: login falha → continuar sem login, capturar o que conseguir
    - WARNING: LLM falha → gerar PDF sem análise
    - INFO: delivery falha → execução é success (delivery é best-effort)
- [X] **11.3.2** Implementar atualização parcial de progresso

  - Atualizar `Execution.logs` a cada fase concluída (não esperar o final)
  - Adicionar campo `progress_percent` no model Execution (0-100)
  - Fases e percentuais:
    - 10%: Execution criada
    - 20%: Browser iniciado
    - 40%: Navegação concluída
    - 60%: Screenshots salvos
    - 75%: Análise LLM concluída
    - 90%: PDF gerado
    - 100%: Delivery executada / concluída
  - Frontend: progress bar na página de detalhes da execução
- [X] **11.3.3** Implementar log estruturado para execuções

  - Substituir `all_logs: list[str]` por log estruturado:
    ```python
    @dataclass
    class ExecutionLogEntry:
        timestamp: datetime
        level: str  # INFO, WARNING, ERROR, FATAL
        phase: str  # browser, screenshots, analysis, pdf, delivery
        message: str
        metadata: dict | None = None
    ```
  - Serializar como JSON para o campo `Execution.logs`
  - Frontend: renderizar logs com cores por nível e agrupamento por fase
- [X] **11.3.4** Adicionar notificação de falhas críticas

  - Se uma execução falhar, verificar se há canal de notificação configurado
  - Enviar alerta com detalhes do erro (por email ou webhook)
  - Configurável por job: `notify_on_failure: bool` (default: true)
  - Incluir link para a execução falhada no frontend

---

## Sprint 12 —Backend Security and Hardening Segurança do Backend e Hardenin

> **Prioridade:** ALTA
> **Objetivo:** Tornar o backend seguro para ambientes de produção, com proteção contra ataques comuns e práticas de segurança enterprise.

### 12.1 Autenticação e Autorização

- [X] **12.1.1** Implementar rate limiting no endpoint de login

- Usar `slowapi` ou middleware custom com Redis
- Limites: 5 tentativas/minuto por IP, 10 tentativas/minuto por email
- Após exceder: retornar 429 Too Many Requests com `Retry-After` header
- Logar tentativas bloqueadas para auditoria

- [X] **12.1.2** Implementar token blacklist para logout seguro

- Nova tabela `token_blacklist` (jti, expires_at)
- Endpoint `POST /api/auth/logout` que adiciona JTI do token à blacklist
- Middleware de validação: verificar se JTI está na blacklist antes de aceitar token
- Cleanup periódico: remover tokens expirados da blacklist

- [X] **12.1.3** Fortalecer requisitos de senha

- Mínimo 12 caracteres (OWASP recommendation)
- Pelo menos 1 maiúscula, 1 minúscula, 1 número, 1 especial
- Validação no schema Pydantic `UserCreate` e `PasswordChange`
- Rejeitar senhas comuns (top 1000 senhas)

- [X] **12.1.4** Implementar account lockout após tentativas falhadas

- Após 5 tentativas falhadas consecutivas, bloquear conta por 15 minutos
- Contador de tentativas em Redis: `login_attempts:{email}`
- Reset do contador após login bem-sucedido
- Endpoint admin para desbloquear conta manualmente

- [X] **12.1.5** Adicionar RBAC (Role-Based Access Control) básico

- Roles: `admin`, `operator`, `viewer`
- Admin: acesso total
- Operator: pode criar/editar jobs e projetos, executar jobs
- Viewer: apenas visualizar execuções e dashboards
- Campo `role` no model User + middleware de autorização

### 12.2 Proteção de Dados

- [X] **12.2.1** Implementar sanitização de inputs em todos os endpoints

- Validar e sanitizar todos os campos string contra injection
- Email recipients: remover newlines/carriage returns (prevenção de email injection)
- Nomes de projeto/job: strip de caracteres especiais perigosos
- URLs: validar formato e protocolo (apenas http/https)

- [X] **12.2.2** Implementar audit log para ações críticas

- Nova tabela `audit_log` (id, user_id, action, resource_type, resource_id, details, ip_address, created_at)
- Ações logadas: login, logout, create/update/delete em qualquer recurso, settings changes
- Middleware FastAPI para capturar automaticamente
- Endpoint `GET /api/audit-logs` para consulta (admin only)

- [X] **12.2.3** Criptografar dados sensíveis em trânsito (channel_config, credentials)

- Verificar que `channel_config` em DeliveryConfig está criptografado
- Verificar que credenciais de projeto estão criptografadas com Fernet
- Nunca retornar senhas/api_keys em responses — mascarar com `****`
- Adicionar header `Strict-Transport-Security` para forçar HTTPS

- [X] **12.2.4** Implementar rotação de chaves de criptografia

- Suporte a múltiplas chaves Fernet (MultiFernet)
- Script de migração: re-criptografar todos os valores com nova chave
- Procedimento documentado em docs/SECURITY.md

### 12.3 Segurança de Infraestrutura

- [X] **12.3.1** Adicionar resource limits nos containers Docker

- Backend: `memory: 1g, cpus: 1.0`
- Worker: `memory: 2g, cpus: 2.0` (navegação consome mais)
- Beat: `memory: 256m, cpus: 0.25`
- PostgreSQL: `memory: 512m`
- Redis: `memory: 256m` (já tem maxmemory no config)

- [X] **12.3.2** Configurar Redis com autenticação

- Adicionar `requirepass` na configuração do Redis
- Atualizar connection strings no Celery e backend
- Garantir que Redis não está exposto externamente

- [X] **12.3.3** Implementar request payload size limits

- FastAPI middleware: limitar body size a 10MB (exceto upload de arquivos)
- Nginx: `client_max_body_size 10m` (reduzir de 50m)
- Validar tamanho de campos JSON no schema (ex: `execution_params` max 50KB)

- [X] **12.3.4** Adicionar security headers via middleware

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `Content-Security-Policy: default-src 'self'`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Permissions-Policy: camera=(), microphone=(), geolocation=()`

---

## Sprint 13 — Melhoria dos Providers LLM e Resiliência de API

> **Prioridade:** MÉDIA-ALTA
> **Objetivo:** Tornar as integrações com LLMs mais robustas, com retry, fallback entre providers, e melhor qualidade de análise.

### 13.1 Resiliência das Chamadas LLM

- [X] **13.1.1** Implementar retry com exponential backoff em todos os providers

  - Criar decorator `@retry_with_backoff(max_retries=3, base_delay=1.0, max_delay=30.0)`
  - Aplicar em `analyze_image()` e `analyze_images()` de cada provider
  - Retries apenas para erros transientes (429 Rate Limit, 500 Server Error, timeout, connection error)
  - Não fazer retry para erros permanentes (401 Unauthorized, 400 Bad Request, 404)
  - Jitter aleatório para evitar thundering herd
- [X] **13.1.2** Implementar fallback automático entre providers

  - Configurar providers de fallback por projeto: `fallback_providers: ['openai', 'google']`
  - Se provider primário falhar após todos os retries, tentar o próximo na lista
  - Log: `"Provider {primary} falhou, tentando fallback {secondary}"`
  - Registrar qual provider realmente foi usado na execução
- [X] **13.1.3** Implementar circuit breaker para APIs de LLM

  - Se um provider falhar N vezes consecutivas (ex: 5), abrir circuit breaker
  - Circuit aberto: pular direto para fallback provider (evitar desperdício de tempo)
  - Após cooldown (ex: 5 min), tentar half-open (1 chamada de teste)
  - Se teste funcionar, fechar circuit; senão, manter aberto mais um período
  - Persistir estado do circuit breaker em Redis
- [X] **13.1.4** Adicionar health check periódico para providers LLM

  - Task Celery a cada 10 min: testar cada provider configurado com prompt mínimo
  - Registrar latência e disponibilidade em Redis
  - Dashboard: status dos providers (online/degraded/offline)
  - Usar dados de health check para selecionar melhor provider automaticamente

### 13.2 Melhorias na Qualidade da Análise

- [X] **13.2.1** Implementar system prompt customizável por job

  - Permitir que o usuário defina system prompt adicional no job
  - Merge com o `_SYSTEM_PROMPT_TEMPLATE` base
  - Usar PromptTemplate vinculado ao job para personalização
  - Variáveis de template: `{{project_name}}`, `{{job_name}}`, `{{url}}`, `{{date}}`
- [X] **13.2.2** Implementar extração de dados tipada (schema enforcement)

  - Definir JSON Schema esperado no job (campo `expected_schema` em execution_params)
  - Instruir o LLM a retornar dados no formato especificado
  - Validar resposta contra o schema após extração
  - Se validação falhar, reenviar com correção: `"Sua resposta não seguiu o schema. Corrija: {errors}"`
- [X] **13.2.3** Adicionar modo "structured output" usando tool/function calling

  - Anthropic: usar tool_use para forçar JSON estruturado
  - OpenAI: usar function_calling ou response_format (json_object)
  - Google: usar response_schema em GenerationConfig
  - Melhora significativa na confiabilidade da extração de dados
- [X] **13.2.4** Implementar comparação de análises entre execuções

  - Armazenar hash + resumo de cada análise
  - Detectar quando análise é significativamente diferente da anterior
  - Marcar mudanças detectadas: `"MUDANÇA DETECTADA: campo X mudou de A para B"`
  - Útil para monitoramento: detectar quando um site muda

### 13.3 Suporte Avançado a Providers

- [X] **13.3.1** Adicionar suporte a OpenAI-compatible APIs (Groq, Together, etc.)

  - Estender `OpenAIProvider` para aceitar `base_url` customizada
  - Configuração no projeto: `provider: 'openai-compatible', base_url: 'https://api.groq.com/openai/v1'`
  - Suportar modelos Groq (Llama), Together (Mixtral), etc.
- [X] **13.3.2** Implementar Ollama provider com streaming e detecção de modelos

  - Endpoint de health check: `GET /api/tags` para listar modelos disponíveis
  - Streaming: suporte a `stream: true` para feedback em tempo real
  - Auto-detecção de modelos com visão (filtrar por capacidade `vision`)
- [X] **13.3.3** Adicionar suporte a AWS Bedrock como provider

  - Provider `BedrockProvider` usando boto3
  - Suporte a Claude no Bedrock, Llama no Bedrock
  - Configuração via AWS credentials (access key, secret key, region)

---

## Sprint 14 — Observabilidade e Monitoramento

> **Prioridade:** MÉDIA
> **Objetivo:** Adicionar visibilidade completa sobre o que acontece no sistema em tempo real, com métricas, alertas e troubleshooting facilitado.

### 14.1 Logging Estruturado

- [ ] **14.1.1** Migrar para logging estruturado (JSON) em todo o backend

  - Instalar e configurar `structlog` ou `python-json-logger`
  - Formato: `{"timestamp": "...", "level": "...", "logger": "...", "message": "...", "extra": {...}}`
  - Adicionar `request_id` (UUID) a cada request HTTP via middleware
  - Propagar `request_id` para tasks Celery via headers
- [ ] **14.1.2** Implementar correlation ID para rastreamento end-to-end

  - Gerar `correlation_id` no request HTTP ou na task Celery
  - Propagar em todas as chamadas internas: repositórios, serviços, LLM calls
  - Incluir `correlation_id` nos logs de todos os componentes
  - Permite reconstruir o fluxo completo de uma execução em qualquer ferramenta de logs
- [ ] **14.1.3** Configurar log levels por módulo

  - Config via variável de ambiente: `LOG_LEVELS=app.modules.agents:DEBUG,app.modules.jobs:INFO`
  - Default: INFO para produção, DEBUG para desenvolvimento
  - Permitir alterar log level em runtime via endpoint admin

### 14.2 Métricas e Dashboards

- [ ] **14.2.1** Adicionar métricas Prometheus via `prometheus-fastapi-instrumentator`

  - Métricas automáticas: request count, latency, error rate por endpoint
  - Métricas custom:
    - `agentvision_executions_total` (counter, labels: status, job_id)
    - `agentvision_execution_duration_seconds` (histogram)
    - `agentvision_llm_tokens_total` (counter, labels: provider, model)
    - `agentvision_screenshots_captured_total` (counter)
    - `agentvision_active_executions` (gauge)
- [ ] **14.2.2** Adicionar health check abrangente

  - `GET /api/health` retornando status de cada componente:
    - PostgreSQL: connection + query test
    - Redis: ping + info memory
    - MinIO: bucket access test
    - Celery: ping workers
  - Status geral: `healthy` se todos OK, `degraded` se algum falhar, `unhealthy` se crítico falhar
- [ ] **14.2.3** Criar dashboard de métricas operacionais no frontend

  - Cards: total execuções hoje, taxa de sucesso, tempo médio, tokens gastos
  - Gráfico: execuções por hora (últimas 24h)
  - Gráfico: duração média por job (top 10)
  - Status dos workers Celery (online/offline)
  - Alertas ativos

### 14.3 Alertas

- [ ] **14.3.1** Implementar sistema de alertas baseado em regras
  - Regras configuráveis:
    - Taxa de falha > 50% nas últimas N execuções
    - Execução com duração > N minutos
    - Worker Celery offline
    - Budget de tokens excedido
  - Canal de alerta: email (via delivery service existente) ou webhook
  - Cooldown entre alertas para evitar spam

---

## Sprint 15 — Otimização de Performance e Escalabilidade

> **Prioridade:** MÉDIA
> **Objetivo:** Preparar a plataforma para cenários de maior escala, com otimizações de banco, cache e processamento.

### 15.1 Otimização de Banco de Dados

- [ ] **15.1.1** Adicionar índices estratégicos nas tabelas

  - `executions`: índice composto em `(job_id, status)`, `(job_id, created_at DESC)`
  - `executions`: índice em `status` para busca por execuções running/pending
  - `jobs`: índice em `(is_active, deleted_at)` para query de jobs ativos
  - `delivery_logs`: índice em `(execution_id, status)`
  - `token_usage`: índice em `(execution_id)`, `(provider, created_at)`
- [ ] **15.1.2** Implementar connection pooling com PgBouncer

  - Adicionar PgBouncer como service no docker-compose.yml
  - Modo transaction pooling (mais eficiente para web apps)
  - Configurar: `default_pool_size=20, max_client_conn=100`
  - Backend e workers se conectam via PgBouncer, não direto ao PostgreSQL
- [ ] **15.1.3** Implementar cache Redis para queries frequentes

  - Cache de dashboard metrics (TTL: 60s)
  - Cache de project/job configs (TTL: 300s, invalidar no update)
  - Cache de settings por categoria (TTL: 300s, invalidar no update)
  - Decorator `@cached(ttl=60)` para facilitar uso
- [ ] **15.1.4** Implementar archiving de execuções antigas

  - Execuções com mais de N dias (configurável, default: 90) movidas para tabela `executions_archive`
  - Task periódica semanal: `archive_old_executions`
  - Manter apenas metadados na archive (logs e extracted_data comprimidos)
  - Limpeza de screenshots/PDFs antigos no MinIO (configurable retention)

### 15.2 Otimização do Worker

- [ ] **15.2.1** Configurar Celery worker com concurrency adequada

  - Worker concurrency configurável via environment variable `CELERY_CONCURRENCY`
  - Default: `--concurrency=2` para máquinas com <4 cores, `4` para >4 cores
  - `--max-tasks-per-child=50` para evitar memory leaks de Playwright
  - `--max-memory-per-child=2000000` (2GB) como safety net
- [ ] **15.2.2** Implementar task routing por tipo

  - Queue `default`: check_and_dispatch, cleanup, archive
  - Queue `execution`: execute_job (tarefas pesadas com browser)
  - Queue `priority`: execute_job de jobs high_priority
  - Configurar workers dedicados por queue no docker-compose
- [ ] **15.2.3** Otimizar reutilização de browser context

  - Manter pool de browser contexts pré-inicializados
  - Em vez de criar/destruir browser a cada execução, reutilizar context do pool
  - Reset de state entre execuções (clear cookies, cache, localStorage)
  - Reduzir tempo de startup de ~3s para ~0.5s por execução

---

## Sprint 16 — Melhorias de Delivery e Canais de Entrega

> **Prioridade:** MÉDIA
> **Objetivo:** Expandir os canais de entrega e tornar o sistema de delivery mais robusto e configurável.

### 16.1 Novos Canais de Entrega

- [ ] **16.1.1** Implementar WebhookChannel

  - Classe `WebhookChannel` estendendo `DeliveryChannel`
  - Enviar POST com JSON payload (execution_data + link para PDF)
  - Configuração: URL, headers customizados, método (POST/PUT), auth (Bearer/Basic)
  - Retry com backoff: 3 tentativas com delays de 1s, 5s, 15s
  - Validar HTTPS obrigatório para webhooks em produção
- [ ] **16.1.2** Implementar SlackChannel

  - Usar Slack Incoming Webhook API
  - Mensagem formatada com Blocks: título, sumário, link para PDF, status badges
  - Configuração: webhook_url, channel (opcional), mention_on_failure (@here)
  - Anexar preview do sumário executivo
- [ ] **16.1.3** Implementar canal de armazenamento em disco/S3

  - Salvar PDF em path configurável (local ou S3 bucket externo)
  - Útil para integração com outros sistemas via filesystem
  - Configuração: path_template com variáveis (`{project}/{job}/{date}/report.pdf`)

### 16.2 Melhorias no Sistema de Delivery

- [ ] **16.2.1** Implementar retry automático com exponential backoff

  - Configuração por delivery config: `max_retries`, `retry_delay_seconds`
  - Backoff: 60s → 120s → 300s (multiplicador: 2.0)
  - Task Celery separada para retry: `retry_failed_delivery`
  - Status intermediário: `retrying` com próximo retry timestamp
- [ ] **16.2.2** Implementar delivery condicional

  - Configurar quando enviar: `always`, `on_success`, `on_failure`, `on_change`
  - `on_change`: só entrega se dados extraídos forem diferentes da última execução
  - Campo `delivery_condition` no DeliveryConfig
  - Avaliação de condição antes de enviar
- [ ] **16.2.3** Implementar template de email customizável

  - Tabela de templates de email (ou usar PromptTemplate com categoria 'email')
  - Variáveis: `{{project_name}}`, `{{job_name}}`, `{{execution_date}}`, `{{summary}}`, `{{status}}`
  - Editor no frontend com preview
  - Template padrão mantido como fallback

---

## Sprint 17 — DevOps e Infraestrutura de Produção

> **Prioridade:** MÉDIA-BAIXA
> **Objetivo:** Preparar a aplicação para deploy em produção com práticas de DevOps modernas.

### 17.1 CI/CD e Qualidade

- [ ] **17.1.1** Adicionar testes unitários para módulos críticos

  - Testes para `LoopDetector`, `ScreenshotClassifier`, `PromptToPlaywright`
  - Testes para `LLM providers` com mock de APIs
  - Testes para `PDFGenerator` com dados de fixture
  - Testes para distributed lock e semáforo
  - Target: >80% coverage para módulo agents
- [ ] **17.1.2** Adicionar testes de integração para o pipeline de execução

  - Mock de browser-use e LLM providers
  - Testar fluxo completo: job → execution → screenshots → analysis → PDF → delivery
  - Testar cenários de falha: browser crash, LLM timeout, MinIO indisponível
  - Testar controle de concorrência: 2 execuções simultâneas do mesmo job
- [ ] **17.1.3** Configurar CI pipeline (GitHub Actions)

  - Steps: lint (ruff), type check (mypy), test (pytest), build (Docker)
  - Security scan: `pip-audit` para vulnerabilidades em dependências
  - Build multi-platform: amd64, arm64
  - Deploy automático para staging em push para `develop`

### 17.2 Monitoramento de Produção

- [ ] **17.2.1** Configurar Sentry para error tracking

  - Integrar `sentry-sdk` no FastAPI e Celery
  - Configurar source maps para frontend
  - Alertas para erros com taxa > threshold
  - Contexto rico: user_id, job_id, execution_id em cada evento
- [ ] **17.2.2** Implementar backup automático do PostgreSQL

  - Script `pg_dump` diário via cron ou Celery Beat task
  - Upload para MinIO (bucket `backups/`)
  - Retenção: 7 diários, 4 semanais, 3 mensais
  - Testar restore periodicamente (documentar procedimento)
- [ ] **17.2.3** Adicionar Grafana + Prometheus stack

  - docker-compose.monitoring.yml com Prometheus + Grafana
  - Dashboard pré-configurado para métricas do AgentVision
  - Alertas Grafana para: execuções falhando, workers offline, disk > 80%

---

## Resumo de Prioridades

| Sprint       | Tema                                                    | Prioridade   | Estimativa  |
| ------------ | ------------------------------------------------------- | ------------ | ----------- |
| **8**  | Controle de Execuções e Proteção contra Duplicidade | CRÍTICA     | 1 semana    |
| **9**  | Otimização de Consumo de Tokens LLM                   | ALTA         | 1.5 semanas |
| **10** | Inteligência de Navegação e Segurança do Agente     | ALTA         | 1.5 semanas |
| **11** | Robustez na Geração de PDFs e Tratamento de Erros     | ALTA         | 1 semana    |
| **12** | Segurança do Backend e Hardening                       | ALTA         | 1.5 semanas |
| **13** | Melhoria dos Providers LLM e Resiliência de API        | MÉDIA-ALTA  | 1 semana    |
| **14** | Observabilidade e Monitoramento                         | MÉDIA       | 1 semana    |
| **15** | Otimização de Performance e Escalabilidade            | MÉDIA       | 1 semana    |
| **16** | Melhorias de Delivery e Canais de Entrega               | MÉDIA       | 1 semana    |
| **17** | DevOps e Infraestrutura de Produção                   | MÉDIA-BAIXA | 1.5 semanas |

---

## Problemas Críticos Identificados (Corrigir Imediatamente)

> Estes problemas existem no código atual e devem ser corrigidos antes ou durante as sprints acima.

1. **Screenshot hash não-determinístico** (`browser_agent.py:205`)

   - `hash(img)` muda entre processos Python — deduplicação quebrada
   - **Fix:** usar `hashlib.sha256(img).hexdigest()`
2. **Nenhuma proteção contra execução duplicada** (`tasks.py:557`)

   - `execute_job.delay(str(job.id), False)` é chamado sem verificar se job já está rodando
   - **Fix:** implementar distributed lock (Sprint 8.1)
3. **Execuções running ficam órfãs se worker crashar** (`tasks.py`)

   - Não há mecanismo de cleanup para execuções stuck em `running`
   - **Fix:** implementar stale execution recovery (Sprint 8.2)
4. **Sem limite de concorrência** — pode estourar recursos do servidor

   - Todos os jobs despachados simultaneamente sem throttling
   - **Fix:** semáforo Redis (Sprint 8.3)
5. **Sem retry nas chamadas LLM** (`llm_provider.py`)

   - Erro 429 (rate limit) ou timeout causa falha imediata
   - **Fix:** exponential backoff (Sprint 13.1)
6. **PDF falha silenciosamente se screenshot for inválido** (`pdf_generator.py`)

   - Imagem corrompida crasha o build do PDF inteiro
   - **Fix:** validação individual (Sprint 11.1)
7. **Prompt do agente genérico demais** (`browser_agent.py:625-683`)

   - Agente pode navegar para qualquer lugar, sem restrição
   - **Fix:** sandbox + prompt assertivo (Sprint 10.2 + 10.3)
8. **Token budget sem controle** — gasto infinito possível

   - Sem limite de tokens por dia/mês; loop do agente pode consumir milhares de tokens
   - **Fix:** budget control (Sprint 9.3)
