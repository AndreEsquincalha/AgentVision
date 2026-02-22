import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import * as projectsService from '@/services/projects';
import type { ProjectListParams } from '@/services/projects';
import type {
  Project,
  ProjectCreate,
  ProjectUpdate,
  PaginatedResponse,
} from '@/types';

// --- Query keys ---

const PROJECT_KEYS = {
  all: ['projects'] as const,
  lists: () => [...PROJECT_KEYS.all, 'list'] as const,
  list: (params: ProjectListParams) =>
    [...PROJECT_KEYS.lists(), params] as const,
  details: () => [...PROJECT_KEYS.all, 'detail'] as const,
  detail: (id: string) => [...PROJECT_KEYS.details(), id] as const,
};

/**
 * Hook para buscar a lista paginada de projetos com filtros.
 */
export function useProjects(params: ProjectListParams = {}) {
  return useQuery<PaginatedResponse<Project>>({
    queryKey: PROJECT_KEYS.list(params),
    queryFn: () => projectsService.getProjects(params),
  });
}

/**
 * Hook para buscar os detalhes de um projeto específico.
 */
export function useProject(id: string) {
  return useQuery<Project>({
    queryKey: PROJECT_KEYS.detail(id),
    queryFn: () => projectsService.getProject(id),
    enabled: !!id,
  });
}

/**
 * Hook de mutation para criar um novo projeto.
 * Invalida a lista de projetos após sucesso.
 */
export function useCreateProject() {
  const queryClient = useQueryClient();

  return useMutation<Project, Error, ProjectCreate>({
    mutationFn: (data: ProjectCreate) => projectsService.createProject(data),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: PROJECT_KEYS.lists() });
      toast.success('Projeto criado com sucesso!');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Erro ao criar projeto.');
    },
  });
}

/**
 * Hook de mutation para atualizar um projeto existente.
 * Invalida a lista e o detalhe do projeto após sucesso.
 */
export function useUpdateProject() {
  const queryClient = useQueryClient();

  return useMutation<Project, Error, { id: string; data: ProjectUpdate }>({
    mutationFn: ({ id, data }) => projectsService.updateProject(id, data),
    onSuccess: async (_result, variables) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: PROJECT_KEYS.lists() }),
        queryClient.invalidateQueries({
          queryKey: PROJECT_KEYS.detail(variables.id),
        }),
      ]);
      toast.success('Projeto atualizado com sucesso!');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Erro ao atualizar projeto.');
    },
  });
}

/**
 * Hook de mutation para excluir um projeto.
 * Invalida a lista de projetos após sucesso.
 */
export function useDeleteProject() {
  const queryClient = useQueryClient();

  return useMutation<void, Error, string>({
    mutationFn: (id: string) => projectsService.deleteProject(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: PROJECT_KEYS.lists() });
      toast.success('Projeto excluído com sucesso!');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Erro ao excluir projeto.');
    },
  });
}

export { PROJECT_KEYS };
