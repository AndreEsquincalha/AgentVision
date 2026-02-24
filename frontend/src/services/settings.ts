import api from '@/services/api';
import { API_ENDPOINTS } from '@/utils/constants';
import type { SMTPConfig } from '@/types';

/**
 * Serviço de Configurações.
 * Encapsula chamadas à API para leitura e atualização
 * de configurações por categoria.
 */

/** Formato retornado pela API de settings */
export interface SettingsGroupResponse {
  category: string;
  settings: Record<string, string>;
}

/**
 * Busca as configurações de uma categoria específica.
 * Retorna o dicionário chave-valor de settings.
 */
export async function getSettings(
  category: string
): Promise<Record<string, string>> {
  const response = await api.get<SettingsGroupResponse>(
    API_ENDPOINTS.SETTINGS.BY_CATEGORY(category)
  );
  return response.data.settings;
}

/**
 * Atualiza as configurações de uma categoria específica.
 * Retorna o dicionário chave-valor atualizado.
 */
export async function updateSettings(
  category: string,
  data: Record<string, string>
): Promise<Record<string, string>> {
  // Backend espera { settings: { ... } }
  const response = await api.put<SettingsGroupResponse>(
    API_ENDPOINTS.SETTINGS.BY_CATEGORY(category),
    { settings: data }
  );
  return response.data.settings;
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
