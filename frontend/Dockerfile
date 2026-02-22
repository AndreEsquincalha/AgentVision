# =============================================================================
# Stage 1: Build
# =============================================================================
FROM node:20-alpine AS build

WORKDIR /app

# Copiar arquivos de dependências
COPY package*.json ./

# Instalar dependências
RUN npm ci

# Copiar código fonte
COPY . .

# Build de produção
RUN npm run build

# =============================================================================
# Stage 2: Produção com Nginx
# =============================================================================
FROM nginx:alpine

# Remover configuração padrão do Nginx
RUN rm /etc/nginx/conf.d/default.conf

# Copiar configuração customizada do Nginx
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copiar arquivos estáticos do build
COPY --from=build /app/dist /usr/share/nginx/html

# Expor porta 80
EXPOSE 80

# Comando padrão
CMD ["nginx", "-g", "daemon off;"]
