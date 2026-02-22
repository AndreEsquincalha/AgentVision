FROM python:3.13-slim

# Variáveis de ambiente para Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Diretório de trabalho
WORKDIR /app

# Instalar dependências do sistema (libpq-dev para psycopg2, etc.)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        build-essential \
        libpq-dev \
        curl \
    && rm -rf /var/lib/apt/lists/*

# Copiar e instalar dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Instalar Playwright e seus navegadores
RUN playwright install --with-deps chromium

# Copiar código da aplicação
COPY . .

# Expor porta do Uvicorn
EXPOSE 8000

# Comando padrão: iniciar Uvicorn
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
