import axios, {
  type AxiosInstance,
  type AxiosError,
  type InternalAxiosRequestConfig,
} from 'axios';
import { API_ENDPOINTS, STORAGE_KEYS } from '@/utils/constants';
import type { TokenResponse, ApiError } from '@/types';

// Flag para evitar múltiplas tentativas de refresh simultâneas
let isRefreshing = false;
// Fila de requisições aguardando o refresh do token
let failedQueue: Array<{
  resolve: (value: string | null) => void;
  reject: (error: unknown) => void;
}> = [];

/**
 * Processa a fila de requisições que falharam durante o refresh do token.
 */
function processQueue(error: unknown, token: string | null = null): void {
  failedQueue.forEach(({ resolve, reject }) => {
    if (error) {
      reject(error);
    } else {
      resolve(token);
    }
  });
  failedQueue = [];
}

/**
 * Instância do Axios configurada para comunicação com o backend.
 * - Base URL aponta para o backend via proxy do Vite em desenvolvimento
 * - Interceptor de request adiciona o Authorization header
 * - Interceptor de response trata 401 com refresh automático do token
 */
const api: AxiosInstance = axios.create({
  baseURL: '',
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
});

// =============================================
// Interceptor de Request
// Adiciona o header Authorization com o access token
// =============================================

api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN);
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error: AxiosError) => {
    return Promise.reject(error);
  }
);

// =============================================
// Interceptor de Response
// Trata erros 401 com refresh automático do token
// Trata erros genéricos com mensagens padronizadas
// =============================================

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError<ApiError>) => {
    const originalRequest = error.config as InternalAxiosRequestConfig & {
      _retry?: boolean;
    };

    // Se o erro for 401 e ainda não tentamos refresh nessa requisição
    if (error.response?.status === 401 && !originalRequest._retry) {
      // Não tenta refresh em endpoints de autenticação
      if (
        originalRequest.url === API_ENDPOINTS.AUTH.LOGIN ||
        originalRequest.url === API_ENDPOINTS.AUTH.REFRESH
      ) {
        return Promise.reject(error);
      }

      // Se já estamos fazendo refresh, coloca a requisição na fila
      if (isRefreshing) {
        return new Promise<string | null>((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then((token) => {
          if (token && originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${token}`;
          }
          return api(originalRequest);
        });
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const newToken = await refreshAccessToken();

        if (newToken) {
          processQueue(null, newToken);

          if (originalRequest.headers) {
            originalRequest.headers.Authorization = `Bearer ${newToken}`;
          }
          return api(originalRequest);
        }

        // Refresh falhou — limpa tokens e redireciona para login
        processQueue(new Error('Sessão expirada'));
        handleSessionExpired();
        return Promise.reject(error);
      } catch (refreshError) {
        processQueue(refreshError);
        handleSessionExpired();
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    // Formata mensagem de erro para outros códigos de status
    const errorMessage = getErrorMessage(error);
    return Promise.reject(new Error(errorMessage));
  }
);

// =============================================
// Função de refresh do access token
// =============================================

/**
 * Tenta renovar o access token usando o refresh token armazenado.
 * Retorna o novo access token ou null se falhar.
 */
async function refreshAccessToken(): Promise<string | null> {
  const refreshToken = localStorage.getItem(STORAGE_KEYS.REFRESH_TOKEN);

  if (!refreshToken) {
    return null;
  }

  try {
    // Usa axios diretamente para evitar interceptors recursivos
    const response = await axios.post<TokenResponse>(
      API_ENDPOINTS.AUTH.REFRESH,
      { refresh_token: refreshToken },
      { headers: { 'Content-Type': 'application/json' } }
    );

    const { access_token, refresh_token } = response.data;

    localStorage.setItem(STORAGE_KEYS.ACCESS_TOKEN, access_token);
    localStorage.setItem(STORAGE_KEYS.REFRESH_TOKEN, refresh_token);

    return access_token;
  } catch {
    return null;
  }
}

// =============================================
// Funções auxiliares
// =============================================

/**
 * Limpa os tokens e redireciona para a tela de login.
 */
function handleSessionExpired(): void {
  localStorage.removeItem(STORAGE_KEYS.ACCESS_TOKEN);
  localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN);

  // Redireciona para login se não estiver já na página
  if (window.location.pathname !== '/login') {
    window.location.href = '/login';
  }
}

/**
 * Extrai a mensagem de erro mais amigável de um AxiosError.
 */
function getErrorMessage(error: AxiosError<ApiError>): string {
  // Mensagem do backend
  if (error.response?.data?.detail) {
    return error.response.data.detail;
  }

  // Mensagens padrão por código de status
  switch (error.response?.status) {
    case 400:
      return 'Requisição inválida. Verifique os dados enviados.';
    case 403:
      return 'Acesso negado. Você não tem permissão para esta ação.';
    case 404:
      return 'Recurso não encontrado.';
    case 409:
      return 'Conflito. O recurso já existe ou está em uso.';
    case 422:
      return 'Dados inválidos. Verifique os campos e tente novamente.';
    case 500:
      return 'Erro interno do servidor. Tente novamente mais tarde.';
    default:
      break;
  }

  // Erro de rede
  if (error.code === 'ERR_NETWORK') {
    return 'Erro de conexão. Verifique sua internet e tente novamente.';
  }

  // Timeout
  if (error.code === 'ECONNABORTED') {
    return 'A requisição demorou demais. Tente novamente.';
  }

  return 'Ocorreu um erro inesperado. Tente novamente.';
}

export default api;
