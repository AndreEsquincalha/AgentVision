import { BrowserRouter, Routes, Route, Navigate } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from '@/contexts/AuthContext';
import { ProtectedRoute } from '@/components/layout/ProtectedRoute';
import Login from '@/pages/Login';
import { ROUTES } from '@/utils/constants';

// Placeholder para a área autenticada (substituído no Sprint 3)
function AuthenticatedPlaceholder() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0F1117]">
      <div className="text-center">
        <h1 className="bg-gradient-to-r from-[#6366F1] to-[#8B5CF6] bg-clip-text text-3xl font-bold text-transparent">
          AgentVision
        </h1>
        <p className="mt-4 text-sm text-[#9CA3AF]">
          Dashboard &mdash; Em construção
        </p>
      </div>
    </div>
  );
}

// Configuração do QueryClient com defaults
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutos
      gcTime: 1000 * 60 * 30, // 30 minutos
      retry: 1,
      refetchOnWindowFocus: false,
    },
    mutations: {
      retry: 0,
    },
  },
});

/**
 * Componente raiz da aplicação AgentVision.
 * Configura providers (QueryClient, Auth) e rotas.
 */
function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            {/* Rota pública — Login */}
            <Route path={ROUTES.LOGIN} element={<Login />} />

            {/* Rotas protegidas — requer autenticação */}
            <Route element={<ProtectedRoute />}>
              <Route
                path={ROUTES.DASHBOARD}
                element={<AuthenticatedPlaceholder />}
              />
              {/* Placeholder para rotas futuras */}
              <Route
                path={ROUTES.PROJECTS}
                element={<AuthenticatedPlaceholder />}
              />
              <Route
                path={ROUTES.PROJECT_DETAIL}
                element={<AuthenticatedPlaceholder />}
              />
              <Route
                path={ROUTES.JOBS}
                element={<AuthenticatedPlaceholder />}
              />
              <Route
                path={ROUTES.JOB_DETAIL}
                element={<AuthenticatedPlaceholder />}
              />
              <Route
                path={ROUTES.EXECUTIONS}
                element={<AuthenticatedPlaceholder />}
              />
              <Route
                path={ROUTES.EXECUTION_DETAIL}
                element={<AuthenticatedPlaceholder />}
              />
              <Route
                path={ROUTES.PROMPTS}
                element={<AuthenticatedPlaceholder />}
              />
              <Route
                path={ROUTES.SETTINGS}
                element={<AuthenticatedPlaceholder />}
              />
            </Route>

            {/* Redirect da raiz para dashboard */}
            <Route
              path="/"
              element={<Navigate to={ROUTES.DASHBOARD} replace />}
            />

            {/* Redirect de rotas desconhecidas para dashboard */}
            <Route
              path="*"
              element={<Navigate to={ROUTES.DASHBOARD} replace />}
            />
          </Routes>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
