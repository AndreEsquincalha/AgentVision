// =============================================
// Tipos TypeScript para todas as entidades do AgentVision
// Baseados no diagrama ER da seção 8.3 do PRD
// =============================================

// --- Enums e tipos de status ---

export type ExecutionStatus = 'pending' | 'running' | 'success' | 'failed';

export type DeliveryStatus = 'pending' | 'sent' | 'failed';

export type ChannelType = 'email' | 'onedrive' | 'webhook';

export type LLMProvider = 'anthropic' | 'openai' | 'google' | 'ollama';

// --- Tipos de LLM ---

export interface LLMModel {
  id: string;
  name: string;
  provider: LLMProvider;
}

export interface LLMConfig {
  provider: LLMProvider;
  model: string;
  apiKey?: string;
  temperature: number;
  maxTokens: number;
  timeout: number;
}

// --- Entidades ---

export interface User {
  id: string;
  email: string;
  name: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface Project {
  id: string;
  name: string;
  base_url: string;
  description: string | null;
  llm_provider: LLMProvider;
  llm_model: string;
  llm_temperature: number;
  llm_max_tokens: number;
  llm_timeout: number;
  is_active: boolean;
  has_credentials: boolean;
  has_llm_api_key: boolean;
  jobs_count?: number;
  active_jobs_count?: number;
  created_at: string;
  updated_at: string;
}

export interface ProjectCreate {
  name: string;
  base_url: string;
  description?: string;
  credentials?: {
    username: string;
    password: string;
  };
  llm_provider: LLMProvider;
  llm_model: string;
  llm_api_key?: string;
  llm_temperature: number;
  llm_max_tokens: number;
  llm_timeout: number;
}

export type ProjectUpdate = Partial<ProjectCreate>;

export interface Job {
  id: string;
  project_id: string;
  project_name?: string;
  name: string;
  cron_expression: string;
  agent_prompt: string;
  prompt_template_id: string | null;
  execution_params: Record<string, unknown> | null;
  is_active: boolean;
  notify_on_failure: boolean;
  delivery_configs?: DeliveryConfig[];
  next_execution?: string | null;
  created_at: string;
  updated_at: string;
}

export interface JobCreate {
  project_id: string;
  name: string;
  cron_expression: string;
  agent_prompt: string;
  prompt_template_id?: string;
  execution_params?: Record<string, unknown>;
  notify_on_failure?: boolean;
  delivery_configs?: DeliveryConfigCreate[];
}

export type JobUpdate = Partial<JobCreate>;

// --- Tipos de logs estruturados ---

export type LogLevel = 'INFO' | 'WARNING' | 'ERROR' | 'FATAL';

export type LogPhase = 'browser' | 'screenshots' | 'analysis' | 'pdf' | 'delivery';

export interface StructuredLogEntry {
  timestamp: string;
  level: LogLevel;
  phase: LogPhase;
  message: string;
  metadata?: Record<string, unknown> | null;
}

// --- Execuções ---

export interface Execution {
  id: string;
  job_id: string;
  job_name?: string;
  project_name?: string;
  status: ExecutionStatus;
  progress_percent: number;
  logs: string | null;
  structured_logs: StructuredLogEntry[] | null;
  extracted_data: Record<string, unknown> | null;
  screenshots_path: string | null;
  pdf_path: string | null;
  is_dry_run: boolean;
  started_at: string | null;
  finished_at: string | null;
  duration_seconds: number | null;
  created_at: string;
  updated_at: string;
}

export interface ExecutionDetail extends Execution {
  delivery_logs?: DeliveryLog[];
}

export interface DeliveryConfig {
  id: string;
  job_id: string;
  channel_type: ChannelType;
  recipients: string[];
  channel_config: Record<string, unknown>;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface DeliveryConfigCreate {
  channel_type: ChannelType;
  recipients: string[];
  channel_config?: Record<string, unknown>;
  is_active?: boolean;
}

export interface DeliveryLog {
  id: string;
  execution_id: string;
  delivery_config_id: string;
  channel_type: ChannelType;
  status: DeliveryStatus;
  error_message: string | null;
  sent_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface PromptTemplate {
  id: string;
  name: string;
  content: string;
  description: string | null;
  category: string | null;
  version: number;
  created_at: string;
  updated_at: string;
}

export interface PromptTemplateCreate {
  name: string;
  content: string;
  description?: string;
  category?: string;
}

export type PromptTemplateUpdate = Partial<PromptTemplateCreate>;

export interface Setting {
  id: string;
  key: string;
  value?: string;
  category: string;
  description: string | null;
  created_at: string;
  updated_at: string;
}

export interface SMTPConfig {
  host: string;
  port: number;
  username: string;
  password: string;
  use_tls: boolean;
  sender_email: string;
}

// --- Tipos de paginação ---

export interface PaginationParams {
  page?: number;
  per_page?: number;
  search?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

// --- Tipos de resposta da API ---

export interface ApiResponse<T> {
  success: boolean;
  message?: string;
  data: T;
}

export interface ApiError {
  detail: string;
  status_code?: number;
}

// --- Tipos de autenticação ---

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface RefreshRequest {
  refresh_token: string;
}

// --- Tipos do Dashboard ---

export interface DashboardSummary {
  active_projects: number;
  active_jobs: number;
  inactive_jobs: number;
  today_executions: number;
  today_success: number;
  today_failed: number;
  today_running: number;
  success_rate_7d: number;
}

export interface UpcomingExecution {
  job_id: string;
  job_name: string;
  project_name: string;
  next_execution: string;
}

export interface RecentFailure {
  execution_id: string;
  job_name: string;
  project_name: string;
  error_summary: string;
  failed_at: string;
}
