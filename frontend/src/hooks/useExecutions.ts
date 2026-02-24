import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import * as executionsService from '@/services/executions';
import type { ExecutionListParams } from '@/services/executions';
import type {
  Execution,
  ExecutionDetail,
  DeliveryLog,
  PaginatedResponse,
} from '@/types';
import { DASHBOARD_KEYS } from '@/hooks/useDashboard';

// --- Query keys ---

const EXECUTION_KEYS = {
  all: ['executions'] as const,
  lists: () => [...EXECUTION_KEYS.all, 'list'] as const,
  list: (params: ExecutionListParams) =>
    [...EXECUTION_KEYS.lists(), params] as const,
  details: () => [...EXECUTION_KEYS.all, 'detail'] as const,
  detail: (id: string) => [...EXECUTION_KEYS.details(), id] as const,
  screenshots: (id: string) =>
    [...EXECUTION_KEYS.all, 'screenshots', id] as const,
  pdf: (id: string) =>
    [...EXECUTION_KEYS.all, 'pdf', id] as const,
};

/**
 * Hook para buscar a lista paginada de execucoes com filtros.
 */
export function useExecutions(params: ExecutionListParams = {}) {
  return useQuery<PaginatedResponse<Execution>>({
    queryKey: EXECUTION_KEYS.list(params),
    queryFn: () => executionsService.getExecutions(params),
  });
}

/**
 * Hook para buscar os detalhes de uma execucao especifica.
 */
export function useExecution(id: string) {
  return useQuery<ExecutionDetail>({
    queryKey: EXECUTION_KEYS.detail(id),
    queryFn: () => executionsService.getExecution(id),
    enabled: !!id,
  });
}

/**
 * Hook para buscar as URLs presigned dos screenshots.
 */
export function useScreenshots(id: string) {
  return useQuery<string[]>({
    queryKey: EXECUTION_KEYS.screenshots(id),
    queryFn: () => executionsService.getScreenshots(id),
    enabled: !!id,
  });
}

/**
 * Hook para buscar a URL presigned do PDF.
 */
export function usePdfUrl(id: string) {
  return useQuery<string>({
    queryKey: EXECUTION_KEYS.pdf(id),
    queryFn: () => executionsService.getPdfUrl(id),
    enabled: !!id,
  });
}

/**
 * Hook de mutation para excluir uma execucao.
 * Invalida a lista de execucoes e o dashboard apos sucesso.
 */
export function useDeleteExecution() {
  const queryClient = useQueryClient();

  return useMutation<void, Error, string>({
    mutationFn: (id: string) => executionsService.deleteExecution(id),
    onSuccess: async () => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: EXECUTION_KEYS.lists() }),
        queryClient.invalidateQueries({ queryKey: DASHBOARD_KEYS.all }),
      ]);
      toast.success('Execução excluída com sucesso!');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Erro ao excluir execução.');
    },
  });
}

/**
 * Hook de mutation para reenviar uma entrega que falhou.
 * Invalida o detalhe da execucao e o dashboard apos sucesso.
 */
export function useRetryDelivery() {
  const queryClient = useQueryClient();

  return useMutation<
    DeliveryLog,
    Error,
    { executionId: string; deliveryLogId: string }
  >({
    mutationFn: ({ executionId, deliveryLogId }) =>
      executionsService.retryDelivery(executionId, deliveryLogId),
    onSuccess: async (_result, variables) => {
      await Promise.all([
        queryClient.invalidateQueries({
          queryKey: EXECUTION_KEYS.detail(variables.executionId),
        }),
        queryClient.invalidateQueries({ queryKey: EXECUTION_KEYS.lists() }),
        queryClient.invalidateQueries({ queryKey: DASHBOARD_KEYS.all }),
      ]);
      toast.success('Reenvio da entrega iniciado com sucesso!');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Erro ao reenviar entrega.');
    },
  });
}

export { EXECUTION_KEYS };
