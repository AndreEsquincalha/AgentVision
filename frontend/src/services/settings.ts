import api from '@/services/api';
import { API_ENDPOINTS } from '@/utils/constants';
import type { Setting, SMTPConfig } from '@/types';

/**
 * Serviço de Configurações.
 * Encapsula chamadas à API para leitura e atualização
 * de configurações por categoria.
 */

/**
 * Busca as configurações de uma categoria específica.
 */
export async function getSettings(
  category: string
): Promise<Setting[]> {
  const response = await api.get<Setting[]>(
    API_ENDPOINTS.SETTINGS.BY_CATEGORY(category)
  );
  return response.data;
}

/**
 * Atualiza as configurações de uma categoria específica.
 */
export async function updateSettings(
  category: string,
  data: Record<string, string | number | boolean>
): Promise<Setting[]> {
  const response = await api.put<Setting[]>(
    API_ENDPOINTS.SETTINGS.BY_CATEGORY(category),
    data
  );
  return response.data;
}

/**
 * Testa a conexão SMTP com as configurações fornecidas.
 * Retorna true se a conexão for bem-sucedida.
 */
export async function testSmtp(
  config: SMTPConfig
): Promise<{ success: boolean; message?: string }> {
  const response = await api.post<{ success: boolean; message?: string }>(
    API_ENDPOINTS.SETTINGS.TEST_SMTP,
    config
  );
  return response.data;
}
