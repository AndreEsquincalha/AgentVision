import type {
  ExecutionStatus,
  DeliveryStatus,
  ChannelType,
  LLMProvider,
  LLMModel,
} from '@/types';

// =============================================
// Rotas da aplicação
// =============================================

export const ROUTES = {
  LOGIN: '/login',
  DASHBOARD: '/dashboard',
  PROJECTS: '/projects',
  PROJECT_DETAIL: '/projects/:id',
  JOBS: '/jobs',
  JOB_DETAIL: '/jobs/:id',
  EXECUTIONS: '/executions',
  EXECUTION_DETAIL: '/executions/:id',
  PROMPTS: '/prompts',
  SETTINGS: '/settings',
} as const;

// =============================================
// Endpoints da API
// =============================================

export const API_ENDPOINTS = {
  // Autenticação
  AUTH: {
    LOGIN: '/api/auth/login',
    REFRESH: '/api/auth/refresh',
    ME: '/api/auth/me',
  },

  // Dashboard
  DASHBOARD: {
    SUMMARY: '/api/dashboard/summary',
    RECENT_EXECUTIONS: '/api/dashboard/recent-executions',
    UPCOMING_EXECUTIONS: '/api/dashboard/upcoming-executions',
    RECENT_FAILURES: '/api/dashboard/recent-failures',
  },

  // Projetos
  PROJECTS: {
    LIST: '/api/projects',
    DETAIL: (id: string) => `/api/projects/${id}`,
  },

  // Jobs
  JOBS: {
    LIST: '/api/jobs',
    DETAIL: (id: string) => `/api/jobs/${id}`,
    TOGGLE: (id: string) => `/api/jobs/${id}/toggle`,
    DRY_RUN: (id: string) => `/api/jobs/${id}/dry-run`,
  },

  // Execuções
  EXECUTIONS: {
    LIST: '/api/executions',
    DETAIL: (id: string) => `/api/executions/${id}`,
    SCREENSHOTS: (id: string) => `/api/executions/${id}/screenshots`,
    PDF: (id: string) => `/api/executions/${id}/pdf`,
    RETRY_DELIVERY: (executionId: string, deliveryLogId: string) =>
      `/api/executions/${executionId}/retry-delivery/${deliveryLogId}`,
  },

  // Prompt Templates
  PROMPTS: {
    LIST: '/api/prompts',
    DETAIL: (id: string) => `/api/prompts/${id}`,
  },

  // Configurações
  SETTINGS: {
    BY_CATEGORY: (category: string) => `/api/settings/${category}`,
    TEST_SMTP: '/api/settings/smtp/test',
  },
} as const;

// =============================================
// Mapeamento de providers e modelos de LLM
// =============================================

export const LLM_PROVIDERS: Record<LLMProvider, string> = {
  anthropic: 'Anthropic',
  openai: 'OpenAI',
  google: 'Google AI',
  ollama: 'Ollama (Local)',
};

export const LLM_MODELS: LLMModel[] = [
  // Anthropic
  { id: 'claude-sonnet-4-20250514', name: 'Claude Sonnet 4', provider: 'anthropic' },
  { id: 'claude-opus-4-20250514', name: 'Claude Opus 4', provider: 'anthropic' },
  { id: 'claude-3-5-sonnet-20241022', name: 'Claude 3.5 Sonnet', provider: 'anthropic' },
  { id: 'claude-3-5-haiku-20241022', name: 'Claude 3.5 Haiku', provider: 'anthropic' },

  // OpenAI
  { id: 'gpt-4o', name: 'GPT-4o', provider: 'openai' },
  { id: 'gpt-4o-mini', name: 'GPT-4o Mini', provider: 'openai' },
  { id: 'gpt-4-turbo', name: 'GPT-4 Turbo', provider: 'openai' },

  // Google
  { id: 'gemini-2.0-flash', name: 'Gemini 2.0 Flash', provider: 'google' },
  { id: 'gemini-1.5-pro', name: 'Gemini 1.5 Pro', provider: 'google' },
  { id: 'gemini-1.5-flash', name: 'Gemini 1.5 Flash', provider: 'google' },

  // Ollama (modelos locais com visão)
  { id: 'llava', name: 'LLaVA', provider: 'ollama' },
  { id: 'bakllava', name: 'BakLLaVA', provider: 'ollama' },
  { id: 'llava-llama3', name: 'LLaVA Llama 3', provider: 'ollama' },
];

/**
 * Retorna os modelos disponíveis para um provider específico.
 */
export function getModelsByProvider(provider: LLMProvider): LLMModel[] {
  return LLM_MODELS.filter((model) => model.provider === provider);
}

// =============================================
// Mapeamento de status para cores e labels
// =============================================

export interface StatusConfig {
  label: string;
  color: string;
  bgClass: string;
  textClass: string;
}

export const EXECUTION_STATUS_MAP: Record<ExecutionStatus, StatusConfig> = {
  pending: {
    label: 'Pendente',
    color: '#6B7280',
    bgClass: 'bg-[#6B7280]/10',
    textClass: 'text-[#6B7280]',
  },
  running: {
    label: 'Em andamento',
    color: '#22D3EE',
    bgClass: 'bg-[#22D3EE]/10',
    textClass: 'text-[#22D3EE]',
  },
  success: {
    label: 'Sucesso',
    color: '#10B981',
    bgClass: 'bg-[#10B981]/10',
    textClass: 'text-[#10B981]',
  },
  failed: {
    label: 'Falha',
    color: '#EF4444',
    bgClass: 'bg-[#EF4444]/10',
    textClass: 'text-[#EF4444]',
  },
};

export const DELIVERY_STATUS_MAP: Record<DeliveryStatus, StatusConfig> = {
  pending: {
    label: 'Pendente',
    color: '#6B7280',
    bgClass: 'bg-[#6B7280]/10',
    textClass: 'text-[#6B7280]',
  },
  sent: {
    label: 'Enviado',
    color: '#10B981',
    bgClass: 'bg-[#10B981]/10',
    textClass: 'text-[#10B981]',
  },
  failed: {
    label: 'Falha',
    color: '#EF4444',
    bgClass: 'bg-[#EF4444]/10',
    textClass: 'text-[#EF4444]',
  },
};

export const CHANNEL_TYPE_MAP: Record<ChannelType, string> = {
  email: 'Email',
  onedrive: 'OneDrive',
  webhook: 'Webhook',
};

// =============================================
// Valores padrão de paginação
// =============================================

export const DEFAULT_PAGE = 1;
export const DEFAULT_PER_PAGE = 10;
export const PER_PAGE_OPTIONS = [10, 25, 50, 100];

// =============================================
// Valores padrão de LLM
// =============================================

export const DEFAULT_LLM_TEMPERATURE = 0.7;
export const DEFAULT_LLM_MAX_TOKENS = 4096;
export const DEFAULT_LLM_TIMEOUT = 120;

// =============================================
// Chaves de armazenamento local
// =============================================

export const STORAGE_KEYS = {
  ACCESS_TOKEN: 'agentvision_access_token',
  REFRESH_TOKEN: 'agentvision_refresh_token',
  SIDEBAR_COLLAPSED: 'agentvision_sidebar_collapsed',
} as const;

// =============================================
// Categorias de Prompt Templates
// =============================================

export const PROMPT_CATEGORIES = [
  { value: 'extraction', label: 'Extração de Dados' },
  { value: 'analysis', label: 'Análise Visual' },
  { value: 'navigation', label: 'Navegação' },
  { value: 'report', label: 'Relatório' },
  { value: 'validation', label: 'Validação' },
  { value: 'general', label: 'Geral' },
] as const;

/**
 * Retorna o label em pt-BR de uma categoria de prompt.
 */
export function getPromptCategoryLabel(category: string | null | undefined): string {
  if (!category) return '-';
  const found = PROMPT_CATEGORIES.find((c) => c.value === category);
  return found?.label ?? category;
}
