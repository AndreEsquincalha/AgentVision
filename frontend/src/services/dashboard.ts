import api from '@/services/api';
import { API_ENDPOINTS } from '@/utils/constants';
import type {
  DashboardSummary,
  Execution,
  UpcomingExecution,
  RecentFailure,
  OperationalMetrics,
} from '@/types';

/**
 * Serviço de dados do Dashboard.
 * Encapsula chamadas à API para buscar métricas e listas do dashboard.
 */

/**
 * Busca o resumo do dashboard: contadores de projetos, jobs, execuções e taxa de sucesso.
 */
export async function getSummary(): Promise<DashboardSummary> {
  const response = await api.get<DashboardSummary>(
    API_ENDPOINTS.DASHBOARD.SUMMARY
  );
  return response.data;
}

/**
 * Busca as últimas execuções realizadas.
 */
export async function getRecentExecutions(): Promise<Execution[]> {
  const response = await api.get<Execution[]>(
    API_ENDPOINTS.DASHBOARD.RECENT_EXECUTIONS
  );
  return response.data;
}

/**
 * Busca as próximas execuções agendadas.
 */
export async function getUpcomingExecutions(): Promise<UpcomingExecution[]> {
  const response = await api.get<UpcomingExecution[]>(
    API_ENDPOINTS.DASHBOARD.UPCOMING_EXECUTIONS
  );
  return response.data;
}

/**
 * Busca as falhas recentes (últimas 24h).
 */
export async function getRecentFailures(): Promise<RecentFailure[]> {
  const response = await api.get<RecentFailure[]>(
    API_ENDPOINTS.DASHBOARD.RECENT_FAILURES
  );
  return response.data;
}

/**
 * Busca métricas operacionais (execuções por hora, duração por job, workers).
 */
export async function getOperationalMetrics(): Promise<OperationalMetrics> {
  const response = await api.get<OperationalMetrics>(
    API_ENDPOINTS.DASHBOARD.OPERATIONAL_METRICS
  );
  return response.data;
}
