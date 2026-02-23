import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import * as promptsService from '@/services/prompts';
import type { PromptListParams } from '@/services/prompts';
import type {
  PromptTemplate,
  PromptTemplateCreate,
  PromptTemplateUpdate,
  PaginatedResponse,
} from '@/types';

// --- Query keys ---

const PROMPT_KEYS = {
  all: ['prompts'] as const,
  lists: () => [...PROMPT_KEYS.all, 'list'] as const,
  list: (params: PromptListParams) =>
    [...PROMPT_KEYS.lists(), params] as const,
  details: () => [...PROMPT_KEYS.all, 'detail'] as const,
  detail: (id: string) => [...PROMPT_KEYS.details(), id] as const,
};

/**
 * Hook para buscar a lista paginada de templates de prompt com filtros.
 */
export function usePrompts(params: PromptListParams = {}) {
  return useQuery<PaginatedResponse<PromptTemplate>>({
    queryKey: PROMPT_KEYS.list(params),
    queryFn: () => promptsService.getPrompts(params),
  });
}

/**
 * Hook para buscar os detalhes de um template específico.
 */
export function usePrompt(id: string) {
  return useQuery<PromptTemplate>({
    queryKey: PROMPT_KEYS.detail(id),
    queryFn: () => promptsService.getPrompt(id),
    enabled: !!id,
  });
}

/**
 * Hook de mutation para criar um novo template de prompt.
 * Invalida a lista de templates após sucesso.
 */
export function useCreatePrompt() {
  const queryClient = useQueryClient();

  return useMutation<PromptTemplate, Error, PromptTemplateCreate>({
    mutationFn: (data: PromptTemplateCreate) =>
      promptsService.createPrompt(data),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: PROMPT_KEYS.lists() });
      toast.success('Template criado com sucesso!');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Erro ao criar template.');
    },
  });
}

/**
 * Hook de mutation para atualizar um template existente.
 * Invalida a lista e o detalhe do template após sucesso.
 */
export function useUpdatePrompt() {
  const queryClient = useQueryClient();

  return useMutation<
    PromptTemplate,
    Error,
    { id: string; data: PromptTemplateUpdate }
  >({
    mutationFn: ({ id, data }) => promptsService.updatePrompt(id, data),
    onSuccess: async (_result, variables) => {
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: PROMPT_KEYS.lists() }),
        queryClient.invalidateQueries({
          queryKey: PROMPT_KEYS.detail(variables.id),
        }),
      ]);
      toast.success('Template atualizado com sucesso!');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Erro ao atualizar template.');
    },
  });
}

/**
 * Hook de mutation para excluir um template de prompt.
 * Invalida a lista de templates após sucesso.
 */
export function useDeletePrompt() {
  const queryClient = useQueryClient();

  return useMutation<void, Error, string>({
    mutationFn: (id: string) => promptsService.deletePrompt(id),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: PROMPT_KEYS.lists() });
      toast.success('Template excluído com sucesso!');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Erro ao excluir template.');
    },
  });
}

export { PROMPT_KEYS };
