# AgentVision

Plataforma de automação que utiliza agentes de IA para navegar em sites, capturar screenshots de análises visuais, analisar o conteúdo com modelos de linguagem com visão, gerar relatórios PDF e entregá-los automaticamente via canais configuráveis.

---

## O que é o AgentVision?

O AgentVision automatiza o processo repetitivo de acessar sites/sistemas, capturar prints de dashboards e análises, interpretar os dados visualmente com IA e distribuir relatórios para stakeholders. Tudo isso de forma agendada e sem intervenção manual.

### Fluxo principal

1. **Navega** — Agente abre navegador headless, acessa o site alvo, faz login e navega até a análise.
2. **Captura** — Identifica o momento ideal e tira screenshots da tela.
3. **Analisa** — Envia os screenshots para uma LLM com visão (Claude, GPT-4o, Gemini, Ollama) que extrai dados e gera insights.
4. **Gera PDF** — Monta um relatório profissional com screenshots, análise e dados extraídos.
5. **Entrega** — Envia o PDF por email (e futuramente por OneDrive, WhatsApp, Webhook).
6. **Registra** — Armazena histórico completo com logs, screenshots, PDF e status de entregas.

---

## Stack

| Camada | Tecnologia |
|---|---|
| Frontend | React 18 + Vite + TypeScript + TailwindCSS + shadcn/ui |
| Backend | Python 3.13 + FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.x + Alembic |
| Banco | PostgreSQL 16 |
| Fila | Celery 5.x + Celery Beat + Redis 7 |
| Storage | MinIO (S3-compatible) |
| Automação | browser-use + Playwright (Chromium headless) |
| IA / LLM | Anthropic, OpenAI, Google AI, Ollama (multi-provider) |
| PDF | ReportLab ou WeasyPrint |
| Auth | JWT (python-jose) + bcrypt (passlib) |
| Containers | Docker + Docker Compose |

---

## Pré-requisitos

- [Docker](https://docs.docker.com/get-docker/) >= 24.x
- [Docker Compose](https://docs.docker.com/compose/install/) >= 2.x
- Git

---

## Setup

### 1. Clonar o repositório

```bash
git clone <repo-url> agentvision
cd agentvision
```

### 2. Configurar variáveis de ambiente

```bash
cp .env.example .env
```

Edite o `.env` com suas configurações:

```env
# PostgreSQL
POSTGRES_HOST=postgres
POSTGRES_PORT=5432
POSTGRES_USER=agentvision
POSTGRES_PASSWORD=sua_senha_segura
POSTGRES_DB=agentvision

# Redis
REDIS_URL=redis://redis:6379/0

# MinIO
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=sua_senha_minio
MINIO_BUCKET=agentvision

# JWT
JWT_SECRET_KEY=sua_chave_secreta_jwt
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Criptografia
ENCRYPTION_KEY=sua_chave_fernet_base64

# CORS
CORS_ORIGINS=http://localhost:3000

# Admin seed
ADMIN_EMAIL=admin@agentvision.com
ADMIN_PASSWORD=sua_senha_admin
ADMIN_NAME=Administrador
```

### 3. Subir os containers

```bash
docker compose up -d
```

Serviços que serão iniciados:

| Serviço | Porta |
|---|---|
| Frontend (React) | `localhost:3000` |
| Backend (FastAPI) | `localhost:8000` |
| PostgreSQL | `localhost:5432` |
| Redis | `localhost:6379` |
| MinIO (API) | `localhost:9000` |
| MinIO (Console) | `localhost:9001` |

### 4. Executar migrações

```bash
docker compose exec backend alembic upgrade head
```

### 5. Executar seed do admin

```bash
docker compose exec backend python -m scripts.seed
```

### 6. Acessar o sistema

- **Frontend:** http://localhost:3000
- **API docs:** http://localhost:8000/docs
- **MinIO console:** http://localhost:9001

Login padrão: `admin@agentvision.com` / senha definida no `.env`

---

## Arquitetura de Diretórios

```
agentvision/
├── docker-compose.yml
├── .env.example
├── README.md
│
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── alembic.ini
│   ├── alembic/
│   │   └── versions/
│   ├── app/
│   │   ├── main.py              # Aplicação FastAPI
│   │   ├── config.py            # Configurações (pydantic-settings)
│   │   ├── database.py          # Engine e session SQLAlchemy
│   │   ├── dependencies.py      # Dependencies do FastAPI
│   │   ├── celery_app.py        # Instância do Celery
│   │   ├── modules/
│   │   │   ├── auth/            # Autenticação (JWT)
│   │   │   ├── projects/        # CRUD de projetos
│   │   │   ├── jobs/            # CRUD de jobs + tasks Celery
│   │   │   ├── executions/      # Histórico de execuções
│   │   │   ├── delivery/        # Canais de entrega (Strategy Pattern)
│   │   │   ├── agents/          # Agente browser, LLM, PDF
│   │   │   ├── prompts/         # Templates de prompts
│   │   │   └── settings/        # Configurações do sistema
│   │   └── shared/              # Models base, utils, storage, exceptions
│   └── scripts/
│       └── seed.py              # Seed do admin
│
├── frontend/
│   ├── Dockerfile
│   ├── package.json
│   └── src/
│       ├── components/          # Componentes reutilizáveis
│       │   ├── ui/              # shadcn/ui customizados
│       │   └── layout/          # Sidebar, Header, MainLayout
│       ├── pages/               # Páginas da aplicação
│       ├── services/            # Chamadas à API (Axios)
│       ├── hooks/               # React hooks customizados
│       ├── contexts/            # AuthContext
│       ├── types/               # TypeScript interfaces
│       └── utils/               # Formatters, constantes
│
└── docs/
    ├── README.md
    └── PRD.md
```

---

## Módulos do Backend

Cada módulo segue a estrutura: `router.py`, `schemas.py`, `models.py`, `service.py`, `repository.py`.

| Módulo | Descrição |
|---|---|
| **auth** | Login via JWT, refresh token, dados do usuário |
| **projects** | CRUD de projetos com configuração de LLM por projeto |
| **jobs** | CRUD de jobs, agendamento cron, dry run, tasks Celery |
| **executions** | Histórico de execuções com screenshots, PDFs e logs |
| **delivery** | Canais de entrega (Strategy Pattern): email, futuro OneDrive/WhatsApp/Webhook |
| **agents** | Agente de navegação (browser-use), análise visual (LLM), geração de PDF |
| **prompts** | Templates de prompts reutilizáveis com versionamento |
| **settings** | Configurações do sistema (SMTP, chaves, etc.) |

---

## Páginas do Frontend

| Página | Descrição |
|---|---|
| Login | Autenticação por email e senha |
| Dashboard | Resumo: projetos ativos, jobs, execuções recentes, alertas |
| Projetos | CRUD de sites alvo com configuração de LLM |
| Jobs | CRUD de agendamentos com cron, prompt e canais de entrega |
| Execuções | Histórico com screenshots, PDF, logs e dados extraídos |
| Prompt Templates | Gerenciamento de templates reutilizáveis |
| Configurações | SMTP e configurações gerais |

---

## Padrões de Arquitetura

- **Repository Pattern** — Acesso a dados isolado por módulo
- **Service Layer** — Regras de negócio separadas dos controllers
- **Strategy Pattern** — Canais de entrega (`DeliveryChannel` abstrato → `EmailChannel`, etc.)
- **Strategy/Factory Pattern** — Providers de LLM (`BaseLLMProvider` → `AnthropicProvider`, `OpenAIProvider`, `GoogleProvider`, `OllamaProvider`)
- **Celery + Celery Beat** — Agendamento e execução assíncrona de jobs

---

## Multi-Provider LLM

Cada projeto pode usar um provider e modelo diferente de LLM:

| Provider | Modelos |
|---|---|
| Anthropic | claude-sonnet-4-20250514, claude-opus-4-20250514, etc. |
| OpenAI | gpt-4o, gpt-4o-mini, etc. |
| Google | gemini-pro, gemini-1.5-pro, etc. |
| Ollama | llava, bakllava, qualquer modelo local com visão |

A configuração é feita por projeto, permitindo usar modelos mais baratos para tarefas simples e mais avançados para análises complexas.

---

## Comandos Úteis

```bash
# Subir todos os serviços
docker compose up -d

# Ver logs de um serviço
docker compose logs -f backend
docker compose logs -f worker

# Executar migrações
docker compose exec backend alembic upgrade head

# Criar nova migração
docker compose exec backend alembic revision --autogenerate -m "descricao"

# Executar seed
docker compose exec backend python -m scripts.seed

# Acessar shell do backend
docker compose exec backend bash

# Rebuild após mudanças
docker compose up -d --build

# Parar tudo
docker compose down

# Parar e remover volumes (APAGA DADOS)
docker compose down -v
```

---

## Convenções de Código

### Backend (Python)

- PEP8 com type hints em todo o código
- Aspas simples
- Variáveis, funções, classes e nomes de arquivos em **inglês**
- Comentários em **português brasileiro**
- Pydantic para validação de dados
- Composição sobre herança

### Frontend (TypeScript/React)

- ESLint + Prettier
- Aspas simples
- React Hooks e componentes funcionais (sem classes)
- Variáveis, funções, componentes e nomes de arquivos em **inglês**
- Interface do usuário em **português brasileiro**

### Banco de Dados

- Toda tabela tem: `id` (UUID), `created_at`, `updated_at`
- Recursos deletáveis usam soft delete (`deleted_at`)

---

## Segurança

- Senhas com bcrypt
- Credenciais de sites alvo criptografadas com Fernet
- API keys de LLM criptografadas com Fernet
- JWT com expiração configurável (access: 30min, refresh: 7 dias)
- CORS restrito ao frontend
- Variáveis sensíveis via `.env`
- MinIO com credenciais dedicadas

---

## Licença

Projeto privado. Todos os direitos reservados.
