## Lista de Tarefas

### Sprint 1 — Infraestrutura e Setup Base

#### 1.1 Configuração do ambiente Docker

- [X] **1.1.1** Criar `docker-compose.yml` com serviços: PostgreSQL, Redis, MinIO
  - Definir volumes persistentes para PostgreSQL e MinIO
  - Configurar variáveis de ambiente para cada serviço
  - Definir network interna para comunicação entre containers
  - Configurar health checks para cada serviço
  - Expor portas: PostgreSQL (5432), Redis (6379), MinIO (9000/9001)

- [X] **1.1.2** Criar `.env.example` com todas as variáveis de ambiente do projeto
  - Variáveis do PostgreSQL (host, port, user, password, database)
  - Variáveis do Redis (host, port)
  - Variáveis do MinIO (endpoint, access_key, secret_key, bucket)
  - Variáveis do JWT (secret_key, algorithm, access_token_expire, refresh_token_expire)
  - Variáveis de criptografia (encryption_key)
  - Variáveis de CORS (allowed_origins)

- [X] **1.1.3** Criar `Dockerfile` do backend
  - Imagem base Python 3.13 slim
  - Instalar dependências do sistema (libpq-dev para psycopg2)
  - Copiar requirements.txt e instalar dependências Python
  - Copiar código da aplicação
  - Comando de inicialização com Uvicorn

- [X] **1.1.4** Criar `Dockerfile` do frontend
  - Stage de build: Node 20 alpine, npm install, npm run build
  - Stage de produção: Nginx alpine servindo os arquivos estáticos
  - Configuração do Nginx para SPA (fallback para index.html)

- [X] **1.1.5** Adicionar serviços backend, frontend, worker e beat ao `docker-compose.yml`
  - Backend: depende de PostgreSQL, Redis, MinIO
  - Frontend: depende de backend
  - Worker Celery: mesmo Dockerfile do backend, comando diferente
  - Celery Beat: mesmo Dockerfile do backend, comando diferente
  - Configurar restart policy (unless-stopped) para todos

#### 1.2 Setup do Backend (FastAPI)

- [X] **1.2.1** Criar `requirements.txt` com todas as dependências
  - fastapi, uvicorn[standard], sqlalchemy, alembic, psycopg2-binary
  - celery[redis], redis, python-jose[cryptography], passlib[bcrypt]
  - pydantic, pydantic-settings, python-multipart
  - boto3 (para MinIO/S3), cryptography (Fernet)
  - browser-use, playwright
  - anthropic, openai, google-generativeai
  - reportlab ou weasyprint (PDF)
  - python-dotenv, httpx

- [X] **1.2.2** Criar `app/config.py` com pydantic-settings
  - Classe `Settings` herdando `BaseSettings`
  - Configurações do banco (DATABASE_URL)
  - Configurações do Redis (REDIS_URL)
  - Configurações do MinIO (endpoint, access_key, secret_key, bucket)
  - Configurações do JWT (secret, algorithm, expirations)
  - Configurações de criptografia (ENCRYPTION_KEY)
  - Configurações de CORS
  - Model_config com env_file=".env"

- [X] **1.2.3** Criar `app/database.py` com engine e session do SQLAlchemy
  - Criar engine assíncrono com create_async_engine ou síncrono com create_engine
  - Criar SessionLocal com sessionmaker
  - Criar Base declarativa para os models
  - Função get_db() como dependency do FastAPI

- [X] **1.2.4** Criar `app/main.py` com a aplicação FastAPI
  - Instanciar FastAPI com título, descrição e versão
  - Configurar CORS middleware
  - Incluir routers de cada módulo com prefixos
  - Endpoint de health check (GET /)
  - Eventos de startup/shutdown se necessário

- [X] **1.2.5** Criar `app/dependencies.py` com dependências compartilhadas
  - Dependency de autenticação (get_current_user)
  - Dependency de sessão do banco (get_db)
  - Dependency de storage (get_storage_client)

- [X] **1.2.6** Configurar Alembic para migrações
  - Executar `alembic init alembic`
  - Configurar `alembic.ini` com URL do banco
  - Configurar `alembic/env.py` para importar os models e a Base
  - Criar migração inicial vazia para validar setup

- [X] **1.2.7** Criar `app/shared/models.py` com base model compartilhado
  - Classe `BaseModel` com campos id (UUID), created_at, updated_at
  - Classe `SoftDeleteModel` herdando BaseModel + deleted_at
  - Configurar updated_at com onupdate automático

- [X] **1.2.8** Criar `app/shared/schemas.py` com schemas compartilhados
  - Schema base com id, created_at, updated_at
  - Schema de paginação (page, per_page, total, items)
  - Schema de resposta padrão (success, message, data)

- [X] **1.2.9** Criar `app/shared/exceptions.py` com exceções customizadas
  - NotFoundException (404)
  - UnauthorizedException (401)
  - ForbiddenException (403)
  - BadRequestException (400)
  - Handler global de exceções para a aplicação FastAPI

- [X] **1.2.10** Criar `app/shared/storage.py` com client MinIO/S3
  - Classe StorageClient com boto3
  - Método upload_file(bucket, key, file_data, content_type)
  - Método download_file(bucket, key)
  - Método get_presigned_url(bucket, key, expiration)
  - Método delete_file(bucket, key)
  - Inicialização do bucket no startup se não existir

- [X] **1.2.11** Criar `app/shared/utils.py` com utilitários
  - Função de criptografia encrypt_value(value) / decrypt_value(encrypted)
  - Função generate_uuid()
  - Função utc_now()

- [X] **1.2.12** Criar `app/celery_app.py` com instância do Celery
  - Instanciar Celery com broker Redis
  - Configurar backend de resultados (Redis)
  - Configurar autodiscover de tasks nos módulos
  - Configurar serialização (json)
  - Configurar timezone (UTC)

#### 1.3 Setup do Frontend (React + Vite)

- [X] **1.3.1** Inicializar projeto com Vite + React + TypeScript
  - `npm create vite@latest frontend -- --template react-ts`
  - Configurar `vite.config.ts` com proxy para API backend
  - Configurar path aliases (@/ para src/)

- [X] **1.3.2** Instalar e configurar TailwindCSS
  - `npm install -D tailwindcss @tailwindcss/vite`
  - Configurar `tailwind.config.ts` com cores customizadas do design system
  - Configurar `index.css` com layers base, components, utilities
  - Adicionar fonte Inter via @import ou link

- [X] **1.3.3** Instalar e configurar shadcn/ui
  - `npx shadcn@latest init`
  - Configurar tema dark como padrão
  - Configurar cores customizadas no CSS variables

- [X] **1.3.4** Instalar dependências do frontend
  - react-router-dom (rotas)
  - axios (HTTP client)
  - lucide-react (ícones)
  - date-fns (formatação de datas)
  - react-hook-form + zod (formulários e validação)
  - @tanstack/react-query (cache e estado de servidor)

- [X] **1.3.5** Criar `src/types/index.ts` com tipos TypeScript
  - Interfaces para todas as entidades (User, Project, Job, Execution, etc.)
  - Tipos de status (ExecutionStatus, DeliveryStatus, ChannelType)
  - Tipos de paginação (PaginatedResponse, PaginationParams)
  - Tipos de API (ApiResponse, ApiError)
  - Tipos de LLM (LLMProvider, LLMModel, LLMConfig)

- [X] **1.3.6** Criar `src/utils/constants.ts` com constantes
  - Rotas da aplicação (ROUTES)
  - Endpoints da API (API_ENDPOINTS)
  - Mapeamento de providers e modelos de LLM
  - Mapeamento de status para cores/labels
  - Valores padrão de paginação

- [X] **1.3.7** Criar `src/utils/formatters.ts` com funções de formatação
  - formatDate(date) — data em pt-BR
  - formatDateTime(date) — data e hora em pt-BR
  - formatDuration(seconds) — duração legível
  - formatStatus(status) — label em português
  - truncateText(text, maxLength)

- [X] **1.3.8** Criar `src/services/api.ts` com instância Axios configurada
  - Base URL apontando para o backend
  - Interceptor de request para adicionar Authorization header
  - Interceptor de response para tratar 401 (refresh token)
  - Interceptor de response para tratar erros genéricos
  - Função de refresh token

---

### Sprint 2 — Autenticação

#### 2.1 Backend — Módulo Auth

- [X] **2.1.1** Criar `modules/auth/models.py` com modelo User
  - Campos: id, email (unique), hashed_password, name, is_active
  - Herdar de SoftDeleteModel (inclui created_at, updated_at, deleted_at)
  - Índice no campo email

- [X] **2.1.2** Criar `modules/auth/schemas.py` com schemas Pydantic
  - LoginRequest (email, password)
  - TokenResponse (access_token, refresh_token, token_type)
  - RefreshRequest (refresh_token)
  - UserResponse (id, email, name, is_active, created_at)
  - UserCreate (email, password, name) — para seed

- [X] **2.1.3** Criar `modules/auth/repository.py` com UserRepository
  - get_by_email(email) → User | None
  - get_by_id(id) → User | None
  - create(user_data) → User

- [X] **2.1.4** Criar `modules/auth/service.py` com AuthService
  - authenticate(email, password) → TokenResponse
  - refresh_token(refresh_token) → TokenResponse
  - Funções auxiliares: create_access_token, create_refresh_token, verify_password, hash_password
  - Decode e validação de token JWT

- [X] **2.1.5** Criar `modules/auth/router.py` com endpoints
  - POST /api/auth/login — login com email e senha
  - POST /api/auth/refresh — renovar access token
  - GET /api/auth/me — retornar dados do usuário autenticado

- [X] **2.1.6** Criar `scripts/seed.py` para seed do usuário admin
  - Criar usuário admin padrão (email: admin@agentvision.com, senha configurável via .env)
  - Verificar se usuário já existe antes de criar
  - Executável via `python -m scripts.seed`

- [X] **2.1.7** Gerar migração Alembic para tabela users
  - `alembic revision --autogenerate -m "create_users_table"`
  - Revisar migração gerada
  - Executar `alembic upgrade head`

#### 2.2 Frontend — Autenticação

- [X] **2.2.1** Criar `src/contexts/AuthContext.tsx`
  - Estado: user, isAuthenticated, isLoading
  - Funções: login, logout, refreshToken
  - Armazenamento de tokens no localStorage (ou httpOnly cookie via backend)
  - Verificação de autenticação no mount (checar token existente)

- [X] **2.2.2** Criar `src/hooks/useAuth.ts`
  - Hook que consome AuthContext
  - Retorna user, isAuthenticated, login, logout, isLoading

- [X] **2.2.3** Criar `src/services/auth.ts` com serviço de autenticação
  - login(email, password) → TokenResponse
  - refresh(refreshToken) → TokenResponse
  - me() → UserResponse

- [X] **2.2.4** Criar `src/pages/Login.tsx`
  - Layout centralizado com card de login
  - Logo AgentVision no topo
  - Campos: email, senha
  - Botão "Entrar"
  - Validação com react-hook-form + zod
  - Mensagem de erro em caso de falha
  - Redirect para dashboard se já autenticado

- [X] **2.2.5** Configurar rotas em `src/App.tsx`
  - Rota pública: /login → Login.tsx
  - Rotas protegidas: /* → MainLayout (requer auth)
  - Redirect automático para /login se não autenticado
  - Redirect de / para /dashboard se autenticado
  - Componente ProtectedRoute para guard

---

### Sprint 3 — Layout e Dashboard

#### 3.1 Frontend — Layout Principal

- [X] **3.1.1** Criar `src/components/layout/Sidebar.tsx`
  - Sidebar fixa à esquerda com largura 256px (colapsada: 64px)
  - Logo AgentVision no topo com gradiente azul→roxo
  - Itens de navegação com ícones Lucide
  - Item ativo com destaque visual (bg e cor do texto)
  - Botão de colapsar/expandir no final
  - Botão de logout
  - Transição suave ao colapsar/expandir
  - Estado de colapsado persistido no localStorage

- [X] **3.1.2** Criar `src/components/layout/Header.tsx`
  - Header fixo no topo da área de conteúdo
  - Título da página atual (dinâmico por rota)
  - Breadcrumb simples (opcional)
  - Área direita: nome do usuário, avatar placeholder

- [X] **3.1.3** Criar `src/components/layout/MainLayout.tsx`
  - Layout flex com Sidebar à esquerda
  - Área de conteúdo à direita com Header fixo e corpo scrollável
  - Outlet do React Router para renderizar páginas
  - Padding consistente na área de conteúdo

#### 3.2 Frontend — Componentes UI Base

- [X] **3.2.1** Configurar componentes shadcn/ui customizados
  - Button (variantes: primary, secondary, destructive, ghost)
  - Input (estilo dark com focus ring)
  - Textarea
  - Select
  - Card
  - Badge (variantes por status)
  - Table
  - Dialog/Modal
  - Dropdown Menu
  - Tooltip
  - Skeleton (loading)
  - Toast/Sonner (notificações)

- [X] **3.2.2** Criar `src/components/ui/StatusBadge.tsx`
  - Componente reutilizável para badges de status
  - Props: status (success, error, running, pending, warning)
  - Mapeamento automático de cores e labels em português
  - Ícone animado para status "running" (Loader2 spin)

- [X] **3.2.3** Criar `src/components/ui/DataTable.tsx`
  - Componente de tabela reutilizável
  - Props: columns, data, loading, pagination
  - Header com sort (opcional)
  - Loading state com Skeleton rows
  - Empty state com mensagem
  - Paginação integrada (anterior/próximo, total de itens)

- [X] **3.2.4** Criar `src/components/ui/PageHeader.tsx`
  - Componente para cabeçalho de página
  - Props: title, description, action (botão)
  - Layout flex entre título e ação

- [X] **3.2.5** Criar `src/components/ui/ConfirmDialog.tsx`
  - Modal de confirmação reutilizável
  - Props: title, description, confirmLabel, variant (danger/default), onConfirm
  - Botões: cancelar e confirmar

#### 3.3 Backend — Endpoints do Dashboard

- [X] **3.3.1** Criar endpoint `GET /api/dashboard/summary`
  - Retorna contagens: projetos ativos, jobs ativos, jobs inativos
  - Contagem de execuções do dia (por status)
  - Taxa de sucesso (últimos 7 dias)

- [X] **3.3.2** Criar endpoint `GET /api/dashboard/recent-executions`
  - Retorna últimas 10 execuções
  - Inclui nome do job, nome do projeto, status, timestamp, duração

- [X] **3.3.3** Criar endpoint `GET /api/dashboard/upcoming-executions`
  - Retorna próximas 10 execuções agendadas
  - Calcula próximo disparo com base no cron de cada job ativo
  - Inclui nome do job, nome do projeto, próximo horário

- [X] **3.3.4** Criar endpoint `GET /api/dashboard/recent-failures`
  - Retorna execuções com falha das últimas 24h
  - Inclui nome do job, projeto, timestamp, resumo do erro

#### 3.4 Frontend — Página Dashboard

- [X] **3.4.1** Criar `src/pages/Dashboard.tsx`
  - Grid de cards de métricas no topo (projetos ativos, jobs ativos, execuções hoje, taxa de sucesso)
  - Cada card com ícone colorido, valor numérico e label
  - Seção "Últimas Execuções" com tabela compacta (job, projeto, status badge, horário, duração)
  - Seção "Próximas Execuções" com lista (job, projeto, horário agendado)
  - Seção "Alertas de Falhas" com lista de falhas recentes (ícone warning, job, erro, horário)
  - Loading states com skeleton
  - Auto-refresh a cada 30 segundos

- [X] **3.4.2** Criar `src/hooks/useDashboard.ts`
  - Hook com React Query para buscar dados do dashboard
  - Queries separadas para summary, recent-executions, upcoming, failures
  - Configurar staleTime e refetchInterval

---

### Sprint 4 — Módulo de Projetos

#### 4.1 Backend — Módulo Projects

- [X] **4.1.1** Criar `modules/projects/models.py` com modelo Project
  - Campos: id, name, base_url, description, encrypted_credentials
  - Campos LLM: llm_provider, llm_model, encrypted_llm_api_key, llm_temperature, llm_max_tokens, llm_timeout
  - Campo is_active (boolean)
  - Herdar de SoftDeleteModel
  - Relacionamento com Jobs (one-to-many)

- [X] **4.1.2** Criar `modules/projects/schemas.py` com schemas Pydantic
  - ProjectCreate (name, base_url, description, credentials, llm_provider, llm_model, llm_api_key, llm_temperature, llm_max_tokens, llm_timeout)
  - ProjectUpdate (todos opcionais)
  - ProjectResponse (todos os campos menos credentials e api_key em texto puro)
  - ProjectListResponse (paginado)
  - Validações: URL válida, temperature entre 0 e 2, max_tokens > 0

- [X] **4.1.3** Criar `modules/projects/repository.py` com ProjectRepository
  - get_all(page, per_page, filters) → lista paginada
  - get_by_id(id) → Project | None
  - create(project_data) → Project
  - update(id, project_data) → Project
  - soft_delete(id) → None
  - count_active() → int

- [X] **4.1.4** Criar `modules/projects/service.py` com ProjectService
  - list_projects(page, per_page, filters) → PaginatedResponse
  - get_project(id) → ProjectResponse
  - create_project(data) → ProjectResponse (criptografar credentials e api_key)
  - update_project(id, data) → ProjectResponse
  - delete_project(id) → None (soft delete + desativar jobs)
  - get_decrypted_credentials(id) → dict (para uso interno pelo agente)
  - get_llm_config(id) → LLMConfig (para uso interno pelo agente)

- [X] **4.1.5** Criar `modules/projects/router.py` com endpoints
  - GET /api/projects — listar projetos (paginado, filtros)
  - GET /api/projects/:id — detalhe do projeto
  - POST /api/projects — criar projeto
  - PUT /api/projects/:id — atualizar projeto
  - DELETE /api/projects/:id — soft delete
  - Todos os endpoints requerem autenticação

- [X] **4.1.6** Gerar migração Alembic para tabela projects
  - `alembic revision --autogenerate -m "create_projects_table"`
  - Revisar e executar migração

#### 4.2 Frontend — Módulo Projetos

- [X] **4.2.1** Criar `src/services/projects.ts` com serviço de API
  - getProjects(params) → PaginatedResponse<Project>
  - getProject(id) → Project
  - createProject(data) → Project
  - updateProject(id, data) → Project
  - deleteProject(id) → void

- [X] **4.2.2** Criar `src/hooks/useProjects.ts` com hooks React Query
  - useProjects(params) — listagem paginada com filtros
  - useProject(id) — detalhe de um projeto
  - useCreateProject() — mutation de criação
  - useUpdateProject() — mutation de atualização
  - useDeleteProject() — mutation de exclusão

- [X] **4.2.3** Criar `src/pages/Projects.tsx` — listagem de projetos
  - PageHeader com título "Projetos" e botão "Novo Projeto"
  - Filtros: campo de busca por nome, select de status
  - DataTable com colunas: nome, URL, provider LLM, jobs ativos, status, ações
  - Ações por linha: visualizar, editar, excluir
  - Paginação
  - Loading e empty states

- [X] **4.2.4** Criar componente `ProjectForm.tsx` (modal ou página)
  - Seção dados básicos: nome, URL base, descrição
  - Seção credenciais: campos de username e password do site alvo
  - Seção configuração LLM: select de provider, select de modelo (dinâmico), campo API key, sliders/inputs para temperature, max_tokens, timeout
  - Validação com react-hook-form + zod
  - Modo criação e edição (preenchimento de dados existentes)
  - Campos sensíveis mascarados no modo edição

- [X] **4.2.5** Criar `src/pages/ProjectDetail.tsx` — detalhe do projeto
  - Informações do projeto em cards
  - Seção de configuração LLM exibida
  - Lista de jobs associados
  - Botões: editar, excluir (com confirmação)

---

### Sprint 5 — Módulo de Jobs

#### 5.1 Backend — Módulo Jobs

- [X] **5.1.1** Criar `modules/jobs/models.py` com modelo Job
  - Campos: id, project_id (FK), name, cron_expression, agent_prompt, prompt_template_id (FK nullable), execution_params (JSON), is_active
  - Herdar de SoftDeleteModel
  - Relacionamentos: Project (many-to-one), Executions (one-to-many), DeliveryConfigs (one-to-many)

- [X] **5.1.2** Criar `modules/jobs/schemas.py` com schemas Pydantic
  - JobCreate (project_id, name, cron_expression, agent_prompt, prompt_template_id, execution_params, delivery_configs)
  - JobUpdate (todos opcionais)
  - JobResponse (todos os campos + nome do projeto)
  - JobListResponse (paginado)
  - Validação de cron expression

- [X] **5.1.3** Criar `modules/jobs/repository.py` com JobRepository
  - get_all(page, per_page, filters) → lista paginada
  - get_by_id(id) → Job | None
  - get_by_project_id(project_id) → lista de Jobs
  - create(job_data) → Job
  - update(id, job_data) → Job
  - soft_delete(id) → None
  - get_active_jobs() → lista de Jobs ativos
  - count_active() → int

- [X] **5.1.4** Criar `modules/jobs/service.py` com JobService
  - list_jobs(page, per_page, filters) → PaginatedResponse
  - get_job(id) → JobResponse
  - create_job(data) → JobResponse
  - update_job(id, data) → JobResponse
  - delete_job(id) → None (soft delete)
  - toggle_active(id, is_active) → JobResponse
  - trigger_dry_run(id) → Execution (dispara task Celery)
  - get_next_execution_time(cron_expression) → datetime

- [X] **5.1.5** Criar `modules/jobs/router.py` com endpoints
  - GET /api/jobs — listar jobs (paginado, filtros por projeto e status)
  - GET /api/jobs/:id — detalhe do job
  - POST /api/jobs — criar job
  - PUT /api/jobs/:id — atualizar job
  - DELETE /api/jobs/:id — soft delete
  - PATCH /api/jobs/:id/toggle — ativar/desativar
  - POST /api/jobs/:id/dry-run — executar dry run

- [X] **5.1.6** Gerar migração Alembic para tabela jobs
  - `alembic revision --autogenerate -m "create_jobs_table"`
  - Revisar e executar migração

#### 5.2 Backend — Módulo Delivery (Config)

- [X] **5.2.1** Criar `modules/delivery/models.py` com modelos DeliveryConfig e DeliveryLog
  - DeliveryConfig: id, job_id (FK), channel_type (enum: email, onedrive, webhook), recipients (JSON), channel_config (JSON), is_active
  - DeliveryLog: id, execution_id (FK), delivery_config_id (FK), channel_type, status (enum: pending, sent, failed), error_message, sent_at
  - Ambos herdando de BaseModel/SoftDeleteModel conforme adequado

- [X] **5.2.2** Criar `modules/delivery/schemas.py` com schemas
  - DeliveryConfigCreate (channel_type, recipients, channel_config)
  - DeliveryConfigUpdate
  - DeliveryConfigResponse
  - DeliveryLogResponse

- [X] **5.2.3** Criar `modules/delivery/repository.py` com DeliveryRepository
  - get_configs_by_job(job_id) → lista de DeliveryConfigs
  - create_config(data) → DeliveryConfig
  - create_log(data) → DeliveryLog
  - get_logs_by_execution(execution_id) → lista de DeliveryLogs

- [X] **5.2.4** Criar `modules/delivery/base_channel.py` com classe abstrata
  - Classe abstrata `DeliveryChannel`
  - Método abstrato `send(execution, pdf_path, config) → DeliveryResult`
  - Classe `DeliveryResult` (success, error_message)

- [X] **5.2.5** Criar `modules/delivery/email_channel.py` com implementação de email
  - Classe `EmailChannel` implementando `DeliveryChannel`
  - Método `send()`: enviar email com PDF anexo via SMTP
  - Configuração SMTP via Settings do banco ou variáveis de ambiente
  - Template básico de email (HTML)

- [X] **5.2.6** Criar `modules/delivery/service.py` com DeliveryService
  - Factory method para instanciar canal correto pelo tipo
  - deliver(execution, delivery_configs) → lista de DeliveryLogs
  - retry_delivery(delivery_log_id) → DeliveryLog

- [X] **5.2.7** Gerar migração Alembic para tabelas delivery_configs e delivery_logs
  - `alembic revision --autogenerate -m "create_delivery_tables"`
  - Revisar e executar migração

#### 5.3 Frontend — Módulo Jobs

- [X] **5.3.1** Criar `src/services/jobs.ts` com serviço de API
  - getJobs(params) → PaginatedResponse<Job>
  - getJob(id) → Job
  - createJob(data) → Job
  - updateJob(id, data) → Job
  - deleteJob(id) → void
  - toggleJob(id, isActive) → Job
  - dryRun(id) → Execution

- [X] **5.3.2** Criar `src/hooks/useJobs.ts` com hooks React Query
  - useJobs(params) — listagem
  - useJob(id) — detalhe
  - useCreateJob() — mutation
  - useUpdateJob() — mutation
  - useDeleteJob() — mutation
  - useToggleJob() — mutation
  - useDryRun() — mutation

- [X] **5.3.3** Criar `src/pages/Jobs.tsx` — listagem de jobs
  - PageHeader com título "Jobs" e botão "Novo Job"
  - Filtros: busca, select de projeto, select de status (ativo/inativo)
  - DataTable com colunas: nome, projeto, cron, próxima execução, status, ações
  - Toggle de ativação inline na tabela
  - Ações: visualizar, editar, dry run, excluir

- [X] **5.3.4** Criar componente `JobForm.tsx` (modal ou página)
  - Select de projeto
  - Campo nome
  - Campo cron expression com helper visual (preview da próxima execução)
  - Textarea para prompt do agente ou select de prompt template
  - Campo JSON para parâmetros de execução
  - Seção de canais de entrega: botão para adicionar canal, tipo (email), destinatários
  - Validação com react-hook-form + zod

- [X] **5.3.5** Criar `src/pages/JobDetail.tsx` — detalhe do job
  - Informações do job em cards
  - Configuração de cron com próxima execução calculada
  - Prompt configurado
  - Canais de entrega configurados
  - Botões: editar, dry run (com loading), toggle ativo, excluir
  - Tabela das últimas execuções do job

---

### Sprint 6 — Módulo de Execuções

#### 6.1 Backend — Módulo Executions

- [X] **6.1.1** Criar `modules/executions/models.py` com modelo Execution
  - Campos: id, job_id (FK), status (enum: pending, running, success, failed), logs (text), extracted_data (JSON), screenshots_path (string), pdf_path (string), is_dry_run (boolean), started_at, finished_at, duration_seconds
  - Herdar de BaseModel (sem soft delete — execuções são registros permanentes)
  - Relacionamentos: Job (many-to-one), DeliveryLogs (one-to-many)

- [X] **6.1.2** Criar `modules/executions/schemas.py` com schemas
  - ExecutionResponse (todos os campos + nome do job + nome do projeto)
  - ExecutionListResponse (paginado, campos reduzidos)
  - ExecutionDetailResponse (completo com delivery logs)
  - ExecutionFilter (job_id, project_id, status, date_from, date_to)

- [X] **6.1.3** Criar `modules/executions/repository.py` com ExecutionRepository
  - get_all(page, per_page, filters) → lista paginada
  - get_by_id(id) → Execution | None
  - get_by_job_id(job_id, limit) → lista de Executions
  - create(data) → Execution
  - update_status(id, status, logs, data) → Execution
  - count_by_status(date_from, date_to) → dict
  - get_recent(limit) → lista de Executions

- [X] **6.1.4** Criar `modules/executions/service.py` com ExecutionService
  - list_executions(page, per_page, filters) → PaginatedResponse
  - get_execution(id) → ExecutionDetailResponse
  - get_screenshot_urls(id) → lista de URLs presigned
  - get_pdf_url(id) → URL presigned
  - create_execution(job_id, is_dry_run) → Execution

- [X] **6.1.5** Criar `modules/executions/router.py` com endpoints
  - GET /api/executions — listar execuções (paginado, filtros)
  - GET /api/executions/:id — detalhe da execução
  - GET /api/executions/:id/screenshots — URLs dos screenshots
  - GET /api/executions/:id/pdf — URL do PDF
  - POST /api/executions/:id/retry-delivery/:delivery_log_id — reenviar entrega
  - Todos requerem autenticação

- [X] **6.1.6** Gerar migração Alembic para tabela executions
  - `alembic revision --autogenerate -m "create_executions_table"`
  - Revisar e executar migração

#### 6.2 Frontend — Módulo Execuções

- [X] **6.2.1** Criar `src/services/executions.ts` com serviço de API
  - getExecutions(params) → PaginatedResponse<Execution>
  - getExecution(id) → ExecutionDetail
  - getScreenshots(id) → string[] (URLs)
  - getPdfUrl(id) → string (URL)
  - retryDelivery(executionId, deliveryLogId) → DeliveryLog

- [X] **6.2.2** Criar `src/hooks/useExecutions.ts` com hooks React Query
  - useExecutions(params) — listagem
  - useExecution(id) — detalhe
  - useScreenshots(id) — screenshots
  - useRetryDelivery() — mutation

- [X] **6.2.3** Criar `src/pages/Executions.tsx` — listagem de execuções
  - PageHeader com título "Execuções"
  - Filtros: select de projeto, select de job, select de status, date range
  - DataTable com colunas: job, projeto, status (badge), início, duração, ações
  - Ação: visualizar detalhes

- [X] **6.2.4** Criar `src/pages/ExecutionDetail.tsx` — detalhe de execução
  - Card de informações gerais (job, projeto, status, início, fim, duração)
  - Seção "Screenshots" — galeria de imagens com lightbox
  - Seção "Relatório PDF" — botão de download
  - Seção "Dados Extraídos" — JSON formatado (expandível/colapsável)
  - Seção "Logs" — textarea readonly com logs completos
  - Seção "Entregas" — tabela com status de cada entrega (canal, status, horário, ação de reenvio se falhou)

---

### Sprint 7 — Módulo de Prompt Templates e Settings

#### 7.1 Backend — Módulo Prompts

- [X] **7.1.1** Criar `modules/prompts/models.py` com modelo PromptTemplate
  - Campos: id, name, content, description, category, version (int, default 1)
  - Herdar de SoftDeleteModel

- [X] **7.1.2** Criar `modules/prompts/schemas.py` com schemas
  - PromptTemplateCreate (name, content, description, category)
  - PromptTemplateUpdate (content, description, category — incrementa versão)
  - PromptTemplateResponse
  - PromptTemplateListResponse (paginado)

- [X] **7.1.3** Criar `modules/prompts/repository.py` com PromptTemplateRepository
  - CRUD padrão com paginação e filtros
  - get_versions(id) → histórico de versões (se implementado como tabela separada ou campo versionado)

- [X] **7.1.4** Criar `modules/prompts/service.py` com PromptTemplateService
  - CRUD com lógica de versionamento (incrementar version ao atualizar)
  - Listagem com filtros por categoria e nome

- [X] **7.1.5** Criar `modules/prompts/router.py` com endpoints
  - GET /api/prompts — listar templates (paginado, filtros)
  - GET /api/prompts/:id — detalhe
  - POST /api/prompts — criar
  - PUT /api/prompts/:id — atualizar (incrementa versão)
  - DELETE /api/prompts/:id — soft delete
  - Todos requerem autenticação

- [X] **7.1.6** Gerar migração Alembic para tabela prompt_templates
  - `alembic revision --autogenerate -m "create_prompt_templates_table"`
  - Revisar e executar migração

#### 7.2 Backend — Módulo Settings

- [X] **7.2.1** Criar `modules/settings/models.py` com modelo Setting
  - Campos: id, key (unique), encrypted_value, category, description
  - Herdar de BaseModel (sem soft delete)
  - Categorias: smtp, general

- [X] **7.2.2** Criar `modules/settings/schemas.py` com schemas
  - SettingCreate (key, value, category, description)
  - SettingUpdate (value)
  - SettingResponse (key, category, description — valor descriptografado apenas quando necessário)
  - SMTPConfigSchema (host, port, username, password, use_tls, sender_email)

- [X] **7.2.3** Criar `modules/settings/repository.py` com SettingRepository
  - get_by_key(key) → Setting | None
  - get_by_category(category) → lista de Settings
  - upsert(key, value, category, description) → Setting

- [X] **7.2.4** Criar `modules/settings/service.py` com SettingService
  - get_settings(category) → dict de configurações
  - update_settings(category, data) → dict
  - get_smtp_config() → SMTPConfig
  - test_smtp_connection(config) → bool

- [X] **7.2.5** Criar `modules/settings/router.py` com endpoints
  - GET /api/settings/:category — obter configurações por categoria
  - PUT /api/settings/:category — atualizar configurações
  - POST /api/settings/smtp/test — testar conexão SMTP
  - Todos requerem autenticação

- [X] **7.2.6** Gerar migração Alembic para tabela settings
  - `alembic revision --autogenerate -m "create_settings_table"`
  - Revisar e executar migração

#### 7.3 Frontend — Prompt Templates e Settings

- [X] **7.3.1** Criar `src/pages/PromptTemplates.tsx`
  - Listagem de templates com filtros por nome e categoria
  - Modal de criação/edição com campos: nome, categoria, descrição, conteúdo (textarea grande)
  - Indicador de versão atual
  - Ações: editar, excluir

- [X] **7.3.2** Criar `src/pages/Settings.tsx`
  - Seção SMTP: host, porta, usuário, senha, TLS toggle, email remetente
  - Botão "Testar Conexão" com feedback visual (loading → sucesso/erro)
  - Botão "Salvar" para persistir configurações
  - Campos sensíveis mascarados

- [X] **7.3.3** Criar `src/services/settings.ts` com serviço de API
  - getSettings(category) → Settings
  - updateSettings(category, data) → Settings
  - testSmtp() → boolean

---

### Sprint 8 — Módulo de Agentes de IA

#### 8.1 Backend — Módulo Agents (LLM Provider)

- [ ] **8.1.1** Criar `modules/agents/llm_provider.py` com Strategy/Factory
  - Classe abstrata `BaseLLMProvider` com método abstrato `analyze_image(image_data, prompt) → AnalysisResult`
  - Classe `AnalysisResult` (text, extracted_data, tokens_used)
  - Implementação `AnthropicProvider` usando SDK anthropic (Claude Vision)
  - Implementação `OpenAIProvider` usando SDK openai (GPT-4o Vision)
  - Implementação `GoogleProvider` usando SDK google-generativeai (Gemini Vision)
  - Implementação `OllamaProvider` usando HTTP requests para API local do Ollama
  - Factory function `get_llm_provider(provider_name, api_key, model, params) → BaseLLMProvider`

- [ ] **8.1.2** Criar `modules/agents/screenshot_manager.py`
  - Classe `ScreenshotManager`
  - Método `save_screenshot(image_bytes, execution_id, index) → str` (retorna path no MinIO)
  - Método `get_screenshot_urls(execution_id) → list[str]` (URLs presigned)
  - Integração com StorageClient

#### 8.2 Backend — Módulo Agents (Browser Agent)

- [ ] **8.2.1** Criar `modules/agents/browser_agent.py` com agente de navegação
  - Classe `BrowserAgent`
  - Inicialização com configurações do projeto (URL, credentials)
  - Método `run(prompt, execution_params) → BrowserResult`
  - Integração com browser-use + Playwright
  - Navegação guiada pelo prompt do agente
  - Captura de screenshots nos momentos identificados como relevantes
  - Retorno: lista de screenshots (bytes), logs de navegação
  - Tratamento de erros e timeout

#### 8.3 Backend — Módulo Agents (Vision Analyzer)

- [ ] **8.3.1** Criar `modules/agents/vision_analyzer.py` com analisador visual
  - Classe `VisionAnalyzer`
  - Inicialização com LLM provider do projeto
  - Método `analyze(screenshots, prompt) → AnalysisResult`
  - Envio de screenshots para LLM com prompt contextual
  - Parsing da resposta: texto de análise + dados estruturados (JSON)
  - Retorno: análise textual, dados extraídos, insights

#### 8.4 Backend — Módulo Agents (PDF Generator)

- [ ] **8.4.1** Criar `modules/agents/pdf_generator.py` com gerador de PDF
  - Classe `PDFGenerator`
  - Método `generate(screenshots, analysis, metadata) → bytes`
  - Layout profissional: capa com título e data, screenshots com legendas, seção de análise, seção de dados extraídos, seção de insights
  - Usar ReportLab ou WeasyPrint
  - Retorno: PDF em bytes

- [ ] **8.4.2** Integrar geração de PDF com armazenamento no MinIO
  - Salvar PDF no MinIO com path: `pdfs/{execution_id}/report.pdf`
  - Atualizar campo pdf_path da Execution

#### 8.5 Backend — Celery Tasks

- [ ] **8.5.1** Criar `modules/jobs/tasks.py` com task principal
  - Task `execute_job(job_id, is_dry_run=False)`
  - Fluxo: criar Execution → iniciar agente → capturar screenshots → salvar no MinIO → analisar com LLM → gerar PDF → salvar PDF → entregar → atualizar Execution
  - Tratamento de erros em cada etapa com logging
  - Atualizar status da Execution ao longo do processo
  - Se dry_run, pular etapa de entrega

- [ ] **8.5.2** Configurar Celery Beat para agendamento dinâmico
  - Usar DatabaseScheduler ou RedBeat para agendamento dinâmico
  - Sincronizar cron de jobs ativos com o Celery Beat
  - Ao ativar/desativar job, atualizar agendamento

---

### Sprint 9 — Integração e Fluxo Completo

#### 9.1 Integração End-to-End

- [ ] **9.1.1** Testar fluxo completo manualmente: criar projeto → criar job → dry run
  - Verificar que o agente navega corretamente
  - Verificar screenshots capturados
  - Verificar análise da LLM
  - Verificar PDF gerado
  - Verificar dados no banco e MinIO

- [ ] **9.1.2** Testar fluxo de agendamento: ativar job → aguardar execução automática
  - Verificar que Celery Beat dispara no horário correto
  - Verificar que o worker executa a task
  - Verificar que a entrega por email é feita

- [ ] **9.1.3** Testar fluxo de entrega: execução completa → email enviado
  - Configurar SMTP via Settings
  - Verificar email recebido com PDF anexo
  - Verificar DeliveryLog com status "sent"

- [ ] **9.1.4** Testar fluxo de erros: simular falha em cada etapa
  - Falha de navegação (URL inválida)
  - Falha de LLM (API key inválida)
  - Falha de entrega (SMTP inválido)
  - Verificar que Execution é marcada como "failed"
  - Verificar logs de erro

#### 9.2 Refinamentos de UX

- [ ] **9.2.1** Adicionar feedback visual para ações assíncronas
  - Toast de sucesso/erro em operações CRUD
  - Loading states em todos os botões de ação
  - Indicador de progresso em dry run (polling de status)

- [ ] **9.2.2** Adicionar empty states informativos em todas as páginas
  - Mensagem amigável quando não há dados
  - Call-to-action relevante (ex: "Crie seu primeiro projeto")

- [ ] **9.2.3** Adicionar responsividade ao layout
  - Sidebar colapsada automaticamente em telas pequenas
  - Tabelas com scroll horizontal em mobile
  - Cards empilhados em mobile

- [ ] **9.2.4** Adicionar validações completas nos formulários
  - Validação de cron expression com feedback (próxima execução)
  - Validação de URL
  - Validação de JSON (parâmetros de execução)
  - Validação de email (destinatários)
  - Feedback visual inline nos campos

#### 9.3 Polimento e Ajustes Finais

- [ ] **9.3.1** Revisar todas as telas seguindo o design system
  - Consistência de espaçamento, cores, tipografia
  - Transições e micro-interações
  - Foco em acessibilidade básica (contraste, focus visible)

- [ ] **9.3.2** Configurar README.md com instruções de setup
  - Pré-requisitos (Docker, Docker Compose)
  - Passos para setup inicial
  - Variáveis de ambiente necessárias
  - Como executar o seed
  - Como acessar o frontend e MinIO console

- [ ] **9.3.3** Revisar e otimizar docker-compose.yml final
  - Volumes persistentes
  - Health checks em todos os serviços
  - Restart policies
  - Limites de memória (se aplicável)
  - Logs configurados

- [ ] **9.3.4** Revisar segurança
  - Verificar que credenciais não estão expostas em logs
  - Verificar CORS
  - Verificar expiração de tokens
  - Verificar criptografia de campos sensíveis
  - Verificar que MinIO não está público

---

### Resumo de Sprints

| Sprint | Foco | Estimativa |
|---|---|---|
| **Sprint 1** | Infraestrutura, Docker, Setup Backend e Frontend | Fundação |
| **Sprint 2** | Autenticação completa (backend + frontend) | Auth |
| **Sprint 3** | Layout principal, componentes UI, Dashboard | UI/Dashboard |
| **Sprint 4** | Módulo Projetos (CRUD backend + frontend) | Projetos |
| **Sprint 5** | Módulo Jobs + Delivery Config (backend + frontend) | Jobs |
| **Sprint 6** | Módulo Execuções (backend + frontend) | Execuções |
| **Sprint 7** | Prompt Templates + Settings (backend + frontend) | Prompts/Config |
| **Sprint 8** | Agentes de IA (LLM, Browser, Vision, PDF, Celery) | Core IA |
| **Sprint 9** | Integração E2E, refinamentos, polimento | Integração |