# AgentVision

Plataforma de automacao que utiliza agentes de IA para navegar em sites via navegadores headless, capturar screenshots, analisar conteudo visual com LLMs (Claude, GPT-4o, Gemini, Ollama), gerar relatorios PDF profissionais e entrega-los automaticamente via canais configuraveis.

## Pre-requisitos

- [Docker](https://docs.docker.com/get-docker/) (versao 24+)
- [Docker Compose](https://docs.docker.com/compose/install/) (versao 2.20+)
- Git

## Setup Inicial

### 1. Clonar o repositorio

```bash
git clone <url-do-repositorio>
cd AgentVision
```

### 2. Configurar variaveis de ambiente

Copie o arquivo de exemplo e ajuste os valores conforme necessario:

```bash
cp .env.example .env
```

**Variaveis obrigatorias que devem ser alteradas no `.env`:**

| Variavel | Descricao | Exemplo |
|---|---|---|
| `POSTGRES_PASSWORD` | Senha do banco de dados PostgreSQL | Uma senha forte e unica |
| `MINIO_SECRET_KEY` | Senha do MinIO (storage S3) | Uma senha forte e unica |
| `JWT_SECRET_KEY` | Chave secreta para assinatura de tokens JWT | String longa e aleatoria |
| `ENCRYPTION_KEY` | Chave Fernet para criptografia de campos sensiveis | Gerar com o comando abaixo |
| `ADMIN_PASSWORD` | Senha do usuario administrador | Uma senha forte |

Para gerar a chave Fernet de criptografia:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Se nao tiver Python instalado localmente, gere apos subir os containers:

```bash
docker compose run --rm backend python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Consulte o arquivo `.env.example` para a lista completa de variaveis disponiveis.

### 3. Subir os servicos

```bash
docker compose up -d --build
```

Na primeira execucao, aguarde o download das imagens Docker e o build dos containers. Isso pode levar alguns minutos.

Verifique se todos os servicos estao saudaveis:

```bash
docker compose ps
```

Todos os servicos devem estar com status `healthy` ou `running`.

### 4. Executar migracoes do banco de dados

```bash
docker compose exec backend alembic upgrade head
```

### 5. Criar usuario administrador (seed)

```bash
docker compose exec backend python -m scripts.seed
```

O usuario sera criado com as credenciais definidas em `ADMIN_EMAIL` e `ADMIN_PASSWORD` no `.env`.

### 6. Acessar a aplicacao

Abra o navegador e acesse:

- **Frontend (aplicacao):** [http://localhost:3000](http://localhost:3000)
- **Swagger (documentacao da API):** [http://localhost:8000/docs](http://localhost:8000/docs)

Faca login com as credenciais configuradas no `.env` (padrao: `admin@agentvision.com` / `admin123`).

## Portas dos Servicos

| Servico | Porta | URL |
|---|---|---|
| Frontend (React + Nginx) | 3000 | http://localhost:3000 |
| Backend API (FastAPI) | 8000 | http://localhost:8000 |
| Swagger (Docs da API) | 8000 | http://localhost:8000/docs |
| ReDoc (Docs alternativa) | 8000 | http://localhost:8000/redoc |
| PostgreSQL | 5432 | localhost:5432 |
| Redis | 6379 | localhost:6379 |
| MinIO API (S3) | 9000 | http://localhost:9000 |
| MinIO Console (UI) | 9001 | http://localhost:9001 |

## Console do MinIO

O MinIO fornece uma interface web para gerenciar o storage de screenshots e PDFs:

1. Acesse [http://localhost:9001](http://localhost:9001)
2. Faca login com as credenciais definidas em `MINIO_ACCESS_KEY` e `MINIO_SECRET_KEY` no `.env`
   - Padrao: `minioadmin` / `minioadmin_secret_password`

## Comandos Uteis

### Gerenciamento dos containers

```bash
# Subir todos os servicos
docker compose up -d

# Subir com rebuild
docker compose up -d --build

# Parar todos os servicos
docker compose down

# Parar e remover volumes (apaga dados!)
docker compose down -v

# Ver status dos servicos
docker compose ps

# Ver logs de um servico especifico
docker compose logs -f backend
docker compose logs -f worker
docker compose logs -f beat
docker compose logs -f frontend
```

### Banco de dados

```bash
# Executar migracoes
docker compose exec backend alembic upgrade head

# Criar nova migracao (apos alterar models)
docker compose exec backend alembic revision --autogenerate -m "descricao da migracao"

# Reverter ultima migracao
docker compose exec backend alembic downgrade -1
```

### Celery (processamento de tarefas)

Os servicos `worker` e `beat` ja iniciam automaticamente com o Docker Compose. Para ver os logs:

```bash
# Logs do worker (executa as tarefas)
docker compose logs -f worker

# Logs do beat (agenda as tarefas)
docker compose logs -f beat
```

### Seed e scripts

```bash
# Criar usuario admin
docker compose exec backend python -m scripts.seed
```

## Arquitetura

```
AgentVision/
├── backend/               # API FastAPI + Celery
│   ├── app/
│   │   ├── modules/       # Modulos de dominio
│   │   │   ├── auth/      # Autenticacao JWT
│   │   │   ├── projects/  # Projetos (sites alvo)
│   │   │   ├── jobs/      # Agendamentos e tarefas
│   │   │   ├── executions/# Historico de execucoes
│   │   │   ├── delivery/  # Canais de entrega (email)
│   │   │   ├── agents/    # Agentes de IA (browser, vision, PDF)
│   │   │   ├── prompts/   # Templates de prompts
│   │   │   ├── settings/  # Configuracoes do sistema
│   │   │   └── dashboard/ # Dashboard com metricas
│   │   ├── shared/        # Modelos base, utils, storage
│   │   ├── config.py      # Configuracoes via pydantic-settings
│   │   ├── database.py    # Engine e sessao SQLAlchemy
│   │   ├── main.py        # Aplicacao FastAPI
│   │   └── celery_app.py  # Instancia do Celery
│   ├── alembic/           # Migracoes do banco de dados
│   ├── scripts/           # Scripts utilitarios (seed)
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/              # SPA React + Vite + TailwindCSS
│   ├── src/
│   │   ├── pages/         # Paginas da aplicacao
│   │   ├── components/    # Componentes reutilizaveis
│   │   ├── services/      # Clientes HTTP (Axios)
│   │   ├── hooks/         # React Query hooks
│   │   ├── contexts/      # Contextos (Auth)
│   │   └── types/         # Tipos TypeScript
│   ├── Dockerfile
│   └── nginx.conf
├── docker-compose.yml     # Orquestracao de todos os servicos
├── .env.example           # Variaveis de ambiente (template)
└── docs/                  # Documentacao do projeto
    ├── PRD.md             # Requisitos do produto
    ├── TASKS.md           # Lista de tarefas por sprint
    └── README.md          # Guia tecnico detalhado
```

## Stack Tecnologica

| Componente | Tecnologia |
|---|---|
| Backend | Python 3.13, FastAPI, SQLAlchemy 2.x, Pydantic v2 |
| Frontend | React, TypeScript, Vite, TailwindCSS, shadcn/ui |
| Banco de Dados | PostgreSQL 16 |
| Fila de Tarefas | Celery 5.x + Redis 7 |
| Storage | MinIO (S3-compatible) |
| Automacao | browser-use + Playwright (Chromium) |
| IA / LLM | Anthropic (Claude), OpenAI (GPT-4o), Google (Gemini), Ollama |
| PDF | ReportLab |
| Proxy / Servidor | Nginx |

## Fluxo de Execucao

1. O **Celery Beat** verifica a cada 60 segundos quais jobs estao agendados
2. Jobs com cron expression correspondente sao enfileirados no **Celery Worker**
3. O **BrowserAgent** navega no site alvo, faz login se necessario, e captura screenshots
4. Screenshots sao salvos no **MinIO**
5. O **VisionAnalyzer** envia os screenshots para o LLM configurado no projeto
6. O LLM retorna analise textual e dados estruturados (JSON)
7. O **PDFGenerator** cria um relatorio profissional com screenshots e analise
8. O PDF e salvo no **MinIO**
9. O **DeliveryService** envia o relatorio via canais configurados (email)
10. O status da execucao e atualizado no banco de dados

## Licenca

Projeto privado. Todos os direitos reservados.
