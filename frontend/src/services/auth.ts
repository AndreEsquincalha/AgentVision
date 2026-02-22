import api from '@/services/api';
import { API_ENDPOINTS } from '@/utils/constants';
import type { TokenResponse, User } from '@/types';

/**
 * Serviço de autenticação.
 * Encapsula todas as chamadas à API relacionadas a autenticação.
 */

/**
 * Realiza login com email e senha.
 * Retorna os tokens de acesso e refresh.
 */
export async function login(
  email: string,
  password: string
): Promise<TokenResponse> {
  const response = await api.post<TokenResponse>(API_ENDPOINTS.AUTH.LOGIN, {
    email,
    password,
  });
  return response.data;
}

/**
 * Renova o access token usando o refresh token.
 */
export async function refresh(refreshToken: string): Promise<TokenResponse> {
  const response = await api.post<TokenResponse>(API_ENDPOINTS.AUTH.REFRESH, {
    refresh_token: refreshToken,
  });
  return response.data;
}

/**
 * Retorna os dados do usuário autenticado.
 */
export async function me(): Promise<User> {
  const response = await api.get<User>(API_ENDPOINTS.AUTH.ME);
  return response.data;
}
