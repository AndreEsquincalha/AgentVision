import { BrowserRouter, Routes, Route, Navigate } from 'react-router';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'sonner';
import { AuthProvider } from '@/contexts/AuthContext';
import { ProtectedRoute } from '@/components/layout/ProtectedRoute';
import { MainLayout } from '@/components/layout/MainLayout';
import { TooltipProvider } from '@/components/ui/tooltip';
import Login from '@/pages/Login';
import Dashboard from '@/pages/Dashboard';
import Projects from '@/pages/Projects';
import ProjectDetail from '@/pages/ProjectDetail';
import Jobs from '@/pages/Jobs';
import JobDetail from '@/pages/JobDetail';
import Executions from '@/pages/Executions';
import ExecutionDetail from '@/pages/ExecutionDetail';
import PromptTemplates from '@/pages/PromptTemplates';
import Settings from '@/pages/Settings';
import { ROUTES } from '@/utils/constants';

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
 * Configura providers (QueryClient, Auth, Tooltip) e rotas.
 * Rotas protegidas renderizam dentro do MainLayout (Sidebar + Header).
 */
function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AuthProvider>
          <TooltipProvider>
            <Routes>
              {/* Rota pública — Login */}
              <Route path={ROUTES.LOGIN} element={<Login />} />

              {/* Rotas protegidas — requer autenticação, usa MainLayout */}
              <Route element={<ProtectedRoute />}>
                <Route element={<MainLayout />}>
                  <Route path={ROUTES.DASHBOARD} element={<Dashboard />} />
                  <Route
                    path={ROUTES.PROJECTS}
                    element={<Projects />}
                  />
                  <Route
                    path={ROUTES.PROJECT_DETAIL}
                    element={<ProjectDetail />}
                  />
                  <Route
                    path={ROUTES.JOBS}
                    element={<Jobs />}
                  />
                  <Route
                    path={ROUTES.JOB_DETAIL}
                    element={<JobDetail />}
                  />
                  <Route
                    path={ROUTES.EXECUTIONS}
                    element={<Executions />}
                  />
                  <Route
                    path={ROUTES.EXECUTION_DETAIL}
                    element={<ExecutionDetail />}
                  />
                  <Route
                    path={ROUTES.PROMPTS}
                    element={<PromptTemplates />}
                  />
                  <Route
                    path={ROUTES.SETTINGS}
                    element={<Settings />}
                  />
                </Route>
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

            {/* Toaster para notificações toast (sonner) */}
            <Toaster
              theme="dark"
              position="top-right"
              richColors
              toastOptions={{
                style: {
                  background: '#1A1D2E',
                  border: '1px solid #2E3348',
                  color: '#F9FAFB',
                },
              }}
            />
          </TooltipProvider>
        </AuthProvider>
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
