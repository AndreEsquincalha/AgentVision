import { useQuery } from '@tanstack/react-query';
import * as dashboardService from '@/services/dashboard';
import type {
  DashboardSummary,
  Execution,
  UpcomingExecution,
  RecentFailure,
} from '@/types';

// --- Query keys ---

const DASHBOARD_KEYS = {
  all: ['dashboard'] as const,
  summary: () => [...DASHBOARD_KEYS.all, 'summary'] as const,
  recentExecutions: () => [...DASHBOARD_KEYS.all, 'recent-executions'] as const,
  upcomingExecutions: () => [...DASHBOARD_KEYS.all, 'upcoming-executions'] as const,
  recentFailures: () => [...DASHBOARD_KEYS.all, 'recent-failures'] as const,
};

// --- Configurações de tempo ---

/** Dados considerados frescos por 30 segundos */
const STALE_TIME = 1000 * 30;

/** Auto-refresh a cada 30 segundos */
const REFETCH_INTERVAL = 1000 * 30;

/**
 * Hook para buscar o resumo do dashboard.
 * Auto-refresh a cada 30 segundos.
 */
export function useDashboardSummary() {
  return useQuery<DashboardSummary>({
    queryKey: DASHBOARD_KEYS.summary(),
    queryFn: dashboardService.getSummary,
    staleTime: STALE_TIME,
    refetchInterval: REFETCH_INTERVAL,
  });
}

/**
 * Hook para buscar as últimas execuções.
 * Auto-refresh a cada 30 segundos.
 */
export function useRecentExecutions() {
  return useQuery<Execution[]>({
    queryKey: DASHBOARD_KEYS.recentExecutions(),
    queryFn: dashboardService.getRecentExecutions,
    staleTime: STALE_TIME,
    refetchInterval: REFETCH_INTERVAL,
  });
}

/**
 * Hook para buscar as próximas execuções agendadas.
 * Auto-refresh a cada 30 segundos.
 */
export function useUpcomingExecutions() {
  return useQuery<UpcomingExecution[]>({
    queryKey: DASHBOARD_KEYS.upcomingExecutions(),
    queryFn: dashboardService.getUpcomingExecutions,
    staleTime: STALE_TIME,
    refetchInterval: REFETCH_INTERVAL,
  });
}

/**
 * Hook para buscar as falhas recentes.
 * Auto-refresh a cada 30 segundos.
 */
export function useRecentFailures() {
  return useQuery<RecentFailure[]>({
    queryKey: DASHBOARD_KEYS.recentFailures(),
    queryFn: dashboardService.getRecentFailures,
    staleTime: STALE_TIME,
    refetchInterval: REFETCH_INTERVAL,
  });
}

export { DASHBOARD_KEYS };
