import api from '@/services/api';
import { API_ENDPOINTS } from '@/utils/constants';
import type {
  Execution,
  ExecutionDetail,
  DeliveryLog,
  PaginatedResponse,
  ExecutionStatus,
} from '@/types';

// --- Tipos de parametros ---

export interface ExecutionListParams {
  page?: number;
  per_page?: number;
  project_id?: string;
  job_id?: string;
  status?: ExecutionStatus;
  date_from?: string;
  date_to?: string;
}

/**
 * Servico de Execucoes.
 * Encapsula chamadas a API para listagem, detalhes,
 * screenshots, PDF e retry de entregas.
 */

/**
 * Busca a lista paginada de execucoes com filtros opcionais.
 */
export async function getExecutions(
  params: ExecutionListParams = {}
): Promise<PaginatedResponse<Execution>> {
  const response = await api.get<PaginatedResponse<Execution>>(
    API_ENDPOINTS.EXECUTIONS.LIST,
    { params }
  );
  return response.data;
}

/**
 * Busca os detalhes de uma execucao especifica, incluindo logs de entrega.
 */
export async function getExecution(id: string): Promise<ExecutionDetail> {
  const response = await api.get<ExecutionDetail>(
    API_ENDPOINTS.EXECUTIONS.DETAIL(id)
  );
  return response.data;
}

/**
 * Busca as URLs presigned dos screenshots de uma execucao.
 * A API retorna { execution_id, urls: string[] }, extraimos apenas as URLs.
 */
export async function getScreenshots(id: string): Promise<string[]> {
  const response = await api.get<{ execution_id: string; urls: string[] }>(
    API_ENDPOINTS.EXECUTIONS.SCREENSHOTS(id)
  );
  return response.data?.urls ?? [];
}

/**
 * Busca a URL presigned do PDF de uma execucao.
 * A API retorna { execution_id, url: string }, extraimos apenas a URL.
 */
export async function getPdfUrl(id: string): Promise<string> {
  const response = await api.get<{ execution_id: string; url: string }>(
    API_ENDPOINTS.EXECUTIONS.PDF(id)
  );
  return response.data?.url ?? '';
}

/**
 * Remove uma execucao (soft delete).
 */
export async function deleteExecution(id: string): Promise<void> {
  await api.delete(API_ENDPOINTS.EXECUTIONS.DETAIL(id));
}

/**
 * Reenvia a entrega de uma execucao que falhou.
 */
export async function retryDelivery(
  executionId: string,
  deliveryLogId: string
): Promise<DeliveryLog> {
  const response = await api.post<DeliveryLog>(
    API_ENDPOINTS.EXECUTIONS.RETRY_DELIVERY(executionId, deliveryLogId)
  );
  return response.data;
}
