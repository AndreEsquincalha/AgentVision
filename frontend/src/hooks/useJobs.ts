import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import * as jobsService from '@/services/jobs';
import type { JobListParams } from '@/services/jobs';
import type {
  Job,
  JobCreate,
  JobUpdate,
  Execution,
  PaginatedResponse,
} from '@/types';
import { DASHBOARD_KEYS } from '@/hooks/useDashboard';

// --- Query keys ---

const JOB_KEYS = {
  all: ['jobs'] as const,
  lists: () => [...JOB_KEYS.all, 'list'] as const,
  list: (params: JobListParams) =>
    [...JOB_KEYS.lists(), params] as const,
  details: () => [...JOB_KEYS.all, 'detail'] as const,
  detail: (id: string) => [...JOB_KEYS.details(), id] as const,
};

/**
 * Hook para buscar a lista paginada de jobs com filtros.
 */
export function useJobs(params: JobListParams = {}) {
  return useQuery<PaginatedResponse<Job>>({
    queryKey: JOB_KEYS.list(params),
    queryFn: () => jobsService.getJobs(params),
  });
}

/**
 * Hook para buscar os detalhes de um job específico.
 */
export function useJob(id: string) {
  return useQuery<Job>({
    queryKey: JOB_KEYS.detail(id),
    queryFn: () => jobsService.getJob(id),
    enabled: !!id,
  });
}

/**
 * Hook de mutation para criar um novo job.
 * Invalida a lista de jobs e o dashboard após sucesso.
 */
export function useCreateJob() {
  const queryClient = useQueryClient();

  return useMutation<Job, Error, JobCreate>({
    mutationFn: (data: JobCreate) => jobsService.createJob(data),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: JOB_KEYS.lists() }),
        queryClient.invalidateQueries({ queryKey: DASHBOARD_KEYS.all }),
      ]);
      toast.success('Job criado com sucesso!');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Erro ao criar job.');
    },
  });
}

/**
 * Hook de mutation para atualizar um job existente.
 * Invalida a lista e o detalhe do job após sucesso.
 */
export function useUpdateJob() {
  const queryClient = useQueryClient();

  return useMutation<Job, Error, { id: string; data: JobUpdate }>({
    mutationFn: ({ id, data }) => jobsService.updateJob(id, data),
    onSuccess: async (_result, variables) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: JOB_KEYS.lists() }),
        queryClient.invalidateQueries({
          queryKey: JOB_KEYS.detail(variables.id),
        }),
        queryClient.invalidateQueries({ queryKey: DASHBOARD_KEYS.all }),
      ]);
      toast.success('Job atualizado com sucesso!');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Erro ao atualizar job.');
    },
  });
}

/**
 * Hook de mutation para excluir um job.
 * Invalida a lista de jobs e o dashboard após sucesso.
 */
export function useDeleteJob() {
  const queryClient = useQueryClient();

  return useMutation<void, Error, string>({
    mutationFn: (id: string) => jobsService.deleteJob(id),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: JOB_KEYS.lists() }),
        queryClient.invalidateQueries({ queryKey: DASHBOARD_KEYS.all }),
      ]);
      toast.success('Job excluido com sucesso!');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Erro ao excluir job.');
    },
  });
}

/**
 * Hook de mutation para alternar o estado de ativação de um job.
 * Invalida a lista e o detalhe do job, e o dashboard.
 */
export function useToggleJob() {
  const queryClient = useQueryClient();

  return useMutation<Job, Error, { id: string; isActive: boolean }>({
    mutationFn: ({ id, isActive }) => jobsService.toggleJob(id, isActive),
    onSuccess: async (result, variables) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: JOB_KEYS.lists() }),
        queryClient.invalidateQueries({
          queryKey: JOB_KEYS.detail(variables.id),
        }),
        queryClient.invalidateQueries({ queryKey: DASHBOARD_KEYS.all }),
      ]);
      toast.success(
        result.is_active ? 'Job ativado com sucesso!' : 'Job desativado com sucesso!'
      );
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Erro ao alterar status do job.');
    },
  });
}

/**
 * Hook de mutation para executar um dry run de um job.
 * Invalida as execuções recentes do dashboard após sucesso.
 */
export function useDryRun() {
  const queryClient = useQueryClient();

  return useMutation<Execution, Error, string>({
    mutationFn: (id: string) => jobsService.dryRun(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: DASHBOARD_KEYS.all });
      toast.success('Dry run iniciado com sucesso! Acompanhe na página de execuções.');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Erro ao iniciar dry run.');
    },
  });
}

export { JOB_KEYS };
