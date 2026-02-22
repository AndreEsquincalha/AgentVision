import {
  createContext,
  useState,
  useEffect,
  useCallback,
  useMemo,
} from 'react';
import type { ReactNode } from 'react';
import type { User } from '@/types';
import { STORAGE_KEYS } from '@/utils/constants';
import * as authService from '@/services/auth';

// --- Tipos do contexto ---

export interface AuthContextData {
  /** Usuário autenticado ou null se não logado */
  user: User | null;
  /** Indica se o usuário está autenticado */
  isAuthenticated: boolean;
  /** Indica se a verificação inicial de autenticação está em andamento */
  isLoading: boolean;
  /** Realiza login com email e senha */
  login: (email: string, password: string) => Promise<void>;
  /** Realiza logout, limpando tokens e estado */
  logout: () => void;
}

// --- Contexto ---

export const AuthContext = createContext<AuthContextData | null>(null);

// --- Provider ---

interface AuthProviderProps {
  children: ReactNode;
}

export function AuthProvider({ children }: AuthProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  const isAuthenticated = user !== null;

  /**
   * Verifica se existe um token armazenado e busca os dados do usuário.
   * Executado uma vez ao montar o provider.
   */
  useEffect(() => {
    async function checkAuth() {
      const token = localStorage.getItem(STORAGE_KEYS.ACCESS_TOKEN);

      if (!token) {
        setIsLoading(false);
        return;
      }

      try {
        const userData = await authService.me();
        setUser(userData);
      } catch {
        // Token inválido ou expirado — limpa o storage
        localStorage.removeItem(STORAGE_KEYS.ACCESS_TOKEN);
        localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN);
        setUser(null);
      } finally {
        setIsLoading(false);
      }
    }

    checkAuth();
  }, []);

  /**
   * Realiza login, armazena os tokens e busca os dados do usuário.
   */
  const login = useCallback(async (email: string, password: string) => {
    const tokens = await authService.login(email, password);

    localStorage.setItem(STORAGE_KEYS.ACCESS_TOKEN, tokens.access_token);
    localStorage.setItem(STORAGE_KEYS.REFRESH_TOKEN, tokens.refresh_token);

    const userData = await authService.me();
    setUser(userData);
  }, []);

  /**
   * Realiza logout, limpando tokens e estado do usuário.
   */
  const logout = useCallback(() => {
    localStorage.removeItem(STORAGE_KEYS.ACCESS_TOKEN);
    localStorage.removeItem(STORAGE_KEYS.REFRESH_TOKEN);
    setUser(null);
  }, []);

  const value = useMemo<AuthContextData>(
    () => ({
      user,
      isAuthenticated,
      isLoading,
      login,
      logout,
    }),
    [user, isAuthenticated, isLoading, login, logout]
  );

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  );
}
