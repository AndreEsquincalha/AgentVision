import { useMemo, memo } from 'react';
import { useNavigate } from 'react-router';
import {
  FolderKanban,
  Briefcase,
  Play,
  TrendingUp,
  AlertTriangle,
  CalendarClock,
  Clock,
} from 'lucide-react';
import {
  useDashboardSummary,
  useRecentExecutions,
  useUpcomingExecutions,
  useRecentFailures,
} from '@/hooks/useDashboard';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { Skeleton } from '@/components/ui/skeleton';
import { formatDateTime, formatDuration, formatRelativeDate } from '@/utils/formatters';
import type { DashboardSummary, Execution, UpcomingExecution, RecentFailure } from '@/types';
import { cn } from '@/lib/utils';

// --- Tipos auxiliares ---

interface MetricCardConfig {
  label: string;
  key: keyof DashboardSummary;
  icon: React.ComponentType<React.SVGProps<SVGSVGElement> & { className?: string }>;
  iconBgColor: string;
  iconColor: string;
  formatValue?: (value: number) => string;
}

// --- Configuração dos cards de métricas ---

const METRIC_CARDS: MetricCardConfig[] = [
  {
    label: 'Projetos Ativos',
    key: 'active_projects',
    icon: FolderKanban,
    iconBgColor: 'bg-[#6366F1]/10',
    iconColor: 'text-[#6366F1]',
  },
  {
    label: 'Jobs Ativos',
    key: 'active_jobs',
    icon: Briefcase,
    iconBgColor: 'bg-[#8B5CF6]/10',
    iconColor: 'text-[#8B5CF6]',
  },
  {
    label: 'Execuções Hoje',
    key: 'today_executions',
    icon: Play,
    iconBgColor: 'bg-[#22D3EE]/10',
    iconColor: 'text-[#22D3EE]',
  },
  {
    label: 'Taxa de Sucesso (7d)',
    key: 'success_rate_7d',
    icon: TrendingUp,
    iconBgColor: 'bg-[#10B981]/10',
    iconColor: 'text-[#10B981]',
    formatValue: (value: number) => `${value.toFixed(1)}%`,
  },
];

// --- Componentes internos ---

/**
 * Card de métrica individual no topo do dashboard.
 */
const MetricCard = memo(function MetricCard({
  label,
  value,
  icon: Icon,
  iconBgColor,
  iconColor,
  loading,
  formatValue,
}: {
  label: string;
  value: number;
  icon: MetricCardConfig['icon'];
  iconBgColor: string;
  iconColor: string;
  loading: boolean;
  formatValue?: (value: number) => string;
}) {
  return (
    <div className="rounded-xl border border-[#2E3348] bg-[#1A1D2E] p-6">
      <div className="flex items-center gap-4">
        <div className={cn('rounded-lg p-2.5', iconBgColor)}>
          <Icon className={cn('size-5', iconColor)} />
        </div>
        <div>
          {loading ? (
            <>
              <Skeleton className="mb-1 h-7 w-16" />
              <Skeleton className="h-4 w-24" />
            </>
          ) : (
            <>
              <p className="text-2xl font-bold text-[#F9FAFB]">
                {formatValue ? formatValue(value) : value}
              </p>
              <p className="text-sm text-[#9CA3AF]">{label}</p>
            </>
          )}
        </div>
      </div>
    </div>
  );
});

/**
 * Seção de últimas execuções — tabela compacta.
 */
const RecentExecutionsSection = memo(function RecentExecutionsSection({
  executions,
  loading,
}: {
  executions: Execution[];
  loading: boolean;
}) {
  const navigate = useNavigate();

  if (loading) {
    return (
      <div className="rounded-xl border border-[#2E3348] bg-[#1A1D2E]">
        <div className="border-b border-[#2E3348] px-6 py-4">
          <h3 className="text-base font-semibold text-[#F9FAFB]">Últimas Execuções</h3>
        </div>
        <div className="divide-y divide-[#2E3348]">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="flex items-center gap-4 px-6 py-3">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-4 w-24" />
              <Skeleton className="h-5 w-20" />
              <Skeleton className="ml-auto h-4 w-16" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-[#2E3348] bg-[#1A1D2E]">
      <div className="border-b border-[#2E3348] px-6 py-4">
        <h3 className="text-base font-semibold text-[#F9FAFB]">Últimas Execuções</h3>
      </div>

      {executions.length === 0 ? (
        <div className="px-6 py-8 text-center">
          <Play className="mx-auto mb-2 size-8 text-[#6B7280]" />
          <p className="text-sm text-[#9CA3AF]">Nenhuma execução recente</p>
        </div>
      ) : (
        <div className="divide-y divide-[#2E3348]">
          {executions.map((execution) => (
            <button
              key={execution.id}
              onClick={() => navigate(`/executions/${execution.id}`)}
              className="flex w-full items-center gap-4 px-6 py-3 text-left transition-colors hover:bg-[#2A2F42]"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-[#F9FAFB]">
                  {execution.job_name ?? 'Job'}
                </p>
                <p className="truncate text-xs text-[#6B7280]">
                  {execution.project_name ?? 'Projeto'}
                </p>
              </div>
              <StatusBadge status={execution.status} />
              <div className="text-right">
                <p className="text-xs text-[#9CA3AF]">
                  {formatRelativeDate(execution.started_at ?? execution.created_at)}
                </p>
                <p className="text-xs text-[#6B7280]">
                  {formatDuration(execution.duration_seconds)}
                </p>
              </div>
            </button>
          ))}
        </div>
      )}
    </div>
  );
});

/**
 * Seção de próximas execuções agendadas.
 */
const UpcomingExecutionsSection = memo(function UpcomingExecutionsSection({
  executions,
  loading,
}: {
  executions: UpcomingExecution[];
  loading: boolean;
}) {
  if (loading) {
    return (
      <div className="rounded-xl border border-[#2E3348] bg-[#1A1D2E]">
        <div className="border-b border-[#2E3348] px-6 py-4">
          <h3 className="text-base font-semibold text-[#F9FAFB]">Próximas Execuções</h3>
        </div>
        <div className="divide-y divide-[#2E3348]">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="flex items-center gap-4 px-6 py-3">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="ml-auto h-4 w-24" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-[#2E3348] bg-[#1A1D2E]">
      <div className="border-b border-[#2E3348] px-6 py-4">
        <div className="flex items-center gap-2">
          <CalendarClock className="size-4 text-[#8B5CF6]" />
          <h3 className="text-base font-semibold text-[#F9FAFB]">Próximas Execuções</h3>
        </div>
      </div>

      {executions.length === 0 ? (
        <div className="px-6 py-8 text-center">
          <CalendarClock className="mx-auto mb-2 size-8 text-[#6B7280]" />
          <p className="text-sm text-[#9CA3AF]">Nenhuma execução agendada</p>
        </div>
      ) : (
        <div className="divide-y divide-[#2E3348]">
          {executions.map((execution) => (
            <div
              key={`${execution.job_id}-${execution.next_execution}`}
              className="flex items-center gap-4 px-6 py-3"
            >
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-[#F9FAFB]">
                  {execution.job_name}
                </p>
                <p className="truncate text-xs text-[#6B7280]">
                  {execution.project_name}
                </p>
              </div>
              <div className="flex items-center gap-1.5 text-right">
                <Clock className="size-3.5 text-[#9CA3AF]" />
                <span className="text-xs text-[#9CA3AF]">
                  {formatDateTime(execution.next_execution)}
                </span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
});

/**
 * Seção de alertas de falhas recentes (últimas 24h).
 */
const FailureAlertsSection = memo(function FailureAlertsSection({
  failures,
  loading,
}: {
  failures: RecentFailure[];
  loading: boolean;
}) {
  const navigate = useNavigate();

  if (loading) {
    return (
      <div className="rounded-xl border border-[#2E3348] bg-[#1A1D2E]">
        <div className="border-b border-[#2E3348] px-6 py-4">
          <h3 className="text-base font-semibold text-[#F9FAFB]">Alertas de Falhas</h3>
        </div>
        <div className="divide-y divide-[#2E3348]">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="flex items-center gap-4 px-6 py-3">
              <Skeleton className="size-5 rounded-full" />
              <Skeleton className="h-4 w-48" />
              <Skeleton className="ml-auto h-4 w-16" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-[#2E3348] bg-[#1A1D2E]">
      <div className="border-b border-[#2E3348] px-6 py-4">
        <div className="flex items-center gap-2">
          <AlertTriangle className="size-4 text-[#F59E0B]" />
          <h3 className="text-base font-semibold text-[#F9FAFB]">Alertas de Falhas</h3>
        </div>
      </div>

      {failures.length === 0 ? (
        <div className="px-6 py-8 text-center">
          <AlertTriangle className="mx-auto mb-2 size-8 text-[#6B7280]" />
          <p className="text-sm text-[#9CA3AF]">Nenhuma falha nas últimas 24h</p>
        </div>
      ) : (
        <div className="divide-y divide-[#2E3348]">
          {failures.map((failure) => (
            <button
              key={failure.execution_id}
              onClick={() => navigate(`/executions/${failure.execution_id}`)}
              className="flex w-full items-center gap-3 px-6 py-3 text-left transition-colors hover:bg-[#2A2F42]"
            >
              <div className="rounded-full bg-[#EF4444]/10 p-1.5">
                <AlertTriangle className="size-3.5 text-[#EF4444]" />
              </div>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-[#F9FAFB]">
                  {failure.job_name}
                </p>
                <p className="truncate text-xs text-[#EF4444]">
                  {failure.error_summary}
                </p>
              </div>
              <span className="shrink-0 text-xs text-[#6B7280]">
                {formatRelativeDate(failure.failed_at)}
              </span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
});

// --- Componente principal ---

/**
 * Página principal do Dashboard.
 * Exibe cards de métricas, últimas execuções, próximas execuções e alertas de falhas.
 * Dados atualizam automaticamente a cada 30 segundos via React Query.
 */
export default function Dashboard() {
  const { data: summary, isPending: summaryLoading } = useDashboardSummary();
  const { data: recentExecutions, isPending: executionsLoading } = useRecentExecutions();
  const { data: upcomingExecutions, isPending: upcomingLoading } = useUpcomingExecutions();
  const { data: recentFailures, isPending: failuresLoading } = useRecentFailures();

  // Dados de métricas com fallback para zero
  const summaryData = useMemo<DashboardSummary>(
    () =>
      summary ?? {
        active_projects: 0,
        active_jobs: 0,
        inactive_jobs: 0,
        today_executions: 0,
        today_success: 0,
        today_failed: 0,
        today_running: 0,
        success_rate_7d: 0,
      },
    [summary]
  );

  return (
    <div className="space-y-8">
      {/* Grid de métricas */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {METRIC_CARDS.map((card) => (
          <MetricCard
            key={card.key}
            label={card.label}
            value={summaryData[card.key] as number}
            icon={card.icon}
            iconBgColor={card.iconBgColor}
            iconColor={card.iconColor}
            loading={summaryLoading}
            formatValue={card.formatValue}
          />
        ))}
      </div>

      {/* Seções de dados */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        {/* Últimas execuções (coluna esquerda, ocupa mais espaço) */}
        <RecentExecutionsSection
          executions={recentExecutions ?? []}
          loading={executionsLoading}
        />

        {/* Coluna direita: próximas execuções + falhas */}
        <div className="space-y-6">
          <UpcomingExecutionsSection
            executions={upcomingExecutions ?? []}
            loading={upcomingLoading}
          />

          <FailureAlertsSection
            failures={recentFailures ?? []}
            loading={failuresLoading}
          />
        </div>
      </div>
    </div>
  );
}
