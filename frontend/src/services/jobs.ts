import api from '@/services/api';
import { API_ENDPOINTS } from '@/utils/constants';
import type {
  Job,
  JobCreate,
  JobUpdate,
  Execution,
  PaginatedResponse,
} from '@/types';

// --- Tipos de parâmetros ---

export interface JobListParams {
  page?: number;
  per_page?: number;
  search?: string;
  project_id?: string;
  is_active?: boolean;
}

/**
 * Serviço de Jobs.
 * Encapsula chamadas à API para CRUD de jobs,
 * toggle de ativação e dry run.
 */

/**
 * Busca a lista paginada de jobs com filtros opcionais.
 */
export async function getJobs(
  params: JobListParams = {}
): Promise<PaginatedResponse<Job>> {
  const response = await api.get<PaginatedResponse<Job>>(
    API_ENDPOINTS.JOBS.LIST,
    { params }
  );
  return response.data;
}

/**
 * Busca os detalhes de um job específico.
 */
export async function getJob(id: string): Promise<Job> {
  const response = await api.get<Job>(API_ENDPOINTS.JOBS.DETAIL(id));
  return response.data;
}

/**
 * Cria um novo job.
 */
export async function createJob(data: JobCreate): Promise<Job> {
  const response = await api.post<Job>(API_ENDPOINTS.JOBS.LIST, data);
  return response.data;
}

/**
 * Atualiza um job existente.
 */
export async function updateJob(
  id: string,
  data: JobUpdate
): Promise<Job> {
  const response = await api.put<Job>(
    API_ENDPOINTS.JOBS.DETAIL(id),
    data
  );
  return response.data;
}

/**
 * Remove um job (soft delete).
 */
export async function deleteJob(id: string): Promise<void> {
  await api.delete(API_ENDPOINTS.JOBS.DETAIL(id));
}

/**
 * Alterna o estado de ativação de um job.
 */
export async function toggleJob(
  id: string,
  isActive: boolean
): Promise<Job> {
  const response = await api.patch<Job>(
    API_ENDPOINTS.JOBS.TOGGLE(id),
    { is_active: isActive }
  );
  return response.data;
}

/**
 * Executa um dry run do job (execução de teste sem entrega).
 */
export async function dryRun(id: string): Promise<Execution> {
  const response = await api.post<Execution>(
    API_ENDPOINTS.JOBS.DRY_RUN(id)
  );
  return response.data;
}
