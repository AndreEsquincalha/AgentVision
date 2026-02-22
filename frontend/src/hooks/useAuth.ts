import { useContext } from 'react';
import { AuthContext } from '@/contexts/AuthContext';
import type { AuthContextData } from '@/contexts/AuthContext';

/**
 * Hook para acessar o contexto de autenticação.
 * Deve ser usado dentro de um AuthProvider.
 *
 * Retorna: user, isAuthenticated, isLoading, login, logout
 */
export function useAuth(): AuthContextData {
  const context = useContext(AuthContext);

  if (!context) {
    throw new Error(
      'useAuth deve ser usado dentro de um AuthProvider. ' +
      'Verifique se o componente está envolto pelo AuthProvider.'
    );
  }

  return context;
}
