import { Navigate, Outlet } from 'react-router';
import { Loader2 } from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { ROUTES } from '@/utils/constants';

/**
 * Componente de guarda de rota que protege rotas autenticadas.
 * Redireciona para /login se o usuário não estiver autenticado.
 * Exibe um spinner enquanto verifica a autenticação.
 */
export function ProtectedRoute() {
  const { isAuthenticated, isLoading } = useAuth();

  // Exibe loading enquanto verifica autenticação
  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#0F1117]">
        <div className="flex flex-col items-center gap-4">
          <Loader2 className="size-8 animate-spin text-[#6366F1]" />
          <p className="text-sm text-[#9CA3AF]">Verificando autenticação...</p>
        </div>
      </div>
    );
  }

  // Redireciona para login se não autenticado
  if (!isAuthenticated) {
    return <Navigate to={ROUTES.LOGIN} replace />;
  }

  // Renderiza a rota filha
  return <Outlet />;
}
