import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { toast } from 'sonner';
import * as settingsService from '@/services/settings';
import type { SMTPConfig } from '@/types';

// --- Query keys ---

const SETTINGS_KEYS = {
  all: ['settings'] as const,
  categories: () => [...SETTINGS_KEYS.all, 'category'] as const,
  category: (category: string) =>
    [...SETTINGS_KEYS.categories(), category] as const,
};

/**
 * Hook para buscar as configurações de uma categoria específica.
 * Retorna um dicionário chave-valor.
 */
export function useSettings(category: string) {
  return useQuery<Record<string, string>>({
    queryKey: SETTINGS_KEYS.category(category),
    queryFn: () => settingsService.getSettings(category),
    enabled: !!category,
  });
}

/**
 * Hook de mutation para atualizar configurações de uma categoria.
 * Invalida o cache da categoria após sucesso.
 */
export function useUpdateSettings() {
  const queryClient = useQueryClient();

  return useMutation<
    Record<string, string>,
    Error,
    { category: string; data: Record<string, string> }
  >({
    mutationFn: ({ category, data }) =>
      settingsService.updateSettings(category, data),
    onSuccess: async (_result, variables) => {
      await queryClient.invalidateQueries({
        queryKey: SETTINGS_KEYS.category(variables.category),
      });
      toast.success('Configurações salvas com sucesso!');
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Erro ao salvar configurações.');
    },
  });
}

/**
 * Hook de mutation para testar a conexão SMTP.
 * Exibe toast de sucesso ou erro com feedback visual.
 */
export function useTestSmtp() {
  return useMutation<
    { success: boolean; message?: string },
    Error,
    SMTPConfig
  >({
    mutationFn: (config: SMTPConfig) => settingsService.testSmtp(config),
    onSuccess: (result) => {
      if (result.success) {
        toast.success('Conexão SMTP testada com sucesso!');
      } else {
        toast.error(result.message || 'Falha ao testar conexão SMTP.');
      }
    },
    onError: (error: Error) => {
      toast.error(error.message || 'Erro ao testar conexão SMTP.');
    },
  });
}

export { SETTINGS_KEYS };
