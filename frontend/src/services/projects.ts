import api from '@/services/api';
import { API_ENDPOINTS } from '@/utils/constants';
import type {
  Project,
  ProjectCreate,
  ProjectUpdate,
  PaginatedResponse,
} from '@/types';

// --- Tipos de parâmetros ---

export interface ProjectListParams {
  page?: number;
  per_page?: number;
  search?: string;
  is_active?: boolean;
}

/**
 * Serviço de Projetos.
 * Encapsula chamadas à API para CRUD de projetos.
 */

/**
 * Busca a lista paginada de projetos com filtros opcionais.
 */
export async function getProjects(
  params: ProjectListParams = {}
): Promise<PaginatedResponse<Project>> {
  const response = await api.get<PaginatedResponse<Project>>(
    API_ENDPOINTS.PROJECTS.LIST,
    { params }
  );
  return response.data;
}

/**
 * Busca os detalhes de um projeto específico.
 */
export async function getProject(id: string): Promise<Project> {
  const response = await api.get<Project>(API_ENDPOINTS.PROJECTS.DETAIL(id));
  return response.data;
}

/**
 * Cria um novo projeto.
 */
export async function createProject(data: ProjectCreate): Promise<Project> {
  const response = await api.post<Project>(API_ENDPOINTS.PROJECTS.LIST, data);
  return response.data;
}

/**
 * Atualiza um projeto existente.
 */
export async function updateProject(
  id: string,
  data: ProjectUpdate
): Promise<Project> {
  const response = await api.put<Project>(
    API_ENDPOINTS.PROJECTS.DETAIL(id),
    data
  );
  return response.data;
}

/**
 * Remove um projeto (soft delete).
 */
export async function deleteProject(id: string): Promise<void> {
  await api.delete(API_ENDPOINTS.PROJECTS.DETAIL(id));
}
