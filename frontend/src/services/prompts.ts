import api from '@/services/api';
import { API_ENDPOINTS } from '@/utils/constants';
import type {
  PromptTemplate,
  PromptTemplateCreate,
  PromptTemplateUpdate,
  PaginatedResponse,
} from '@/types';

// --- Tipos de parâmetros ---

export interface PromptListParams {
  page?: number;
  per_page?: number;
  search?: string;
  category?: string;
}

/**
 * Serviço de Prompt Templates.
 * Encapsula chamadas à API para CRUD de templates de prompt.
 */

/**
 * Busca a lista paginada de templates com filtros opcionais.
 */
export async function getPrompts(
  params: PromptListParams = {}
): Promise<PaginatedResponse<PromptTemplate>> {
  const response = await api.get<PaginatedResponse<PromptTemplate>>(
    API_ENDPOINTS.PROMPTS.LIST,
    { params }
  );
  return response.data;
}

/**
 * Busca os detalhes de um template específico.
 */
export async function getPrompt(id: string): Promise<PromptTemplate> {
  const response = await api.get<PromptTemplate>(
    API_ENDPOINTS.PROMPTS.DETAIL(id)
  );
  return response.data;
}

/**
 * Cria um novo template de prompt.
 */
export async function createPrompt(
  data: PromptTemplateCreate
): Promise<PromptTemplate> {
  const response = await api.post<PromptTemplate>(
    API_ENDPOINTS.PROMPTS.LIST,
    data
  );
  return response.data;
}

/**
 * Atualiza um template de prompt existente.
 */
export async function updatePrompt(
  id: string,
  data: PromptTemplateUpdate
): Promise<PromptTemplate> {
  const response = await api.put<PromptTemplate>(
    API_ENDPOINTS.PROMPTS.DETAIL(id),
    data
  );
  return response.data;
}

/**
 * Remove um template de prompt.
 */
export async function deletePrompt(id: string): Promise<void> {
  await api.delete(API_ENDPOINTS.PROMPTS.DETAIL(id));
}
