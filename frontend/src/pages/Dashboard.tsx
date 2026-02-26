import { useMemo, memo } from 'react';
import { useNavigate } from 'react-router';
import {
  FolderKanban,
  CalendarClock,
  History,
  TrendingUp,
  AlertTriangle,
  Clock,
  Cpu,
  Coins,
  Timer,
  CircleDot,
} from 'lucide-react';
import {
  useDashboardSummary,
  useRecentExecutions,
  useUpcomingExecutions,
  useRecentFailures,
  useOperationalMetrics,
} from '@/hooks/useDashboard';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { Skeleton } from '@/components/ui/skeleton';
import { formatDateTime, formatDuration, formatRelativeDate } from '@/utils/formatters';
import type {
  DashboardSummary,
  Execution,
  UpcomingExecution,
  RecentFailure,
  ExecutionsPerHour,
  DurationByJob,
  CeleryWorkerStatus,
} from '@/types';
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
    icon: CalendarClock,
    iconBgColor: 'bg-[#8B5CF6]/10',
    iconColor: 'text-[#8B5CF6]',
  },
  {
    label: 'Execuções Hoje',
    key: 'today_executions',
    icon: History,
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
    <div className="rounded-xl border border-[#2E3348] bg-[#1A1D2E] p-6 transition-colors hover:border-[#6366F1]/30">
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
          <History className="mx-auto mb-2 size-8 text-[#6B7280]" />
          <p className="text-sm text-[#9CA3AF]">Nenhuma execução recente</p>
        </div>
      ) : (
        <div className="divide-y divide-[#2E3348]">
          {executions.map((execution) => (
            <button
              key={execution.id}
              onClick={() => navigate(`/executions/${execution.id}`)}
              className="flex w-full items-center gap-4 px-6 py-3 text-left transition-colors hover:bg-[#2A2F42] focus:outline-none focus-visible:bg-[#2A2F42] focus-visible:ring-1 focus-visible:ring-[#6366F1]"
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
              className="flex w-full items-center gap-3 px-6 py-3 text-left transition-colors hover:bg-[#2A2F42] focus:outline-none focus-visible:bg-[#2A2F42] focus-visible:ring-1 focus-visible:ring-[#6366F1]"
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

/**
 * Gráfico de barras de execuções por hora (últimas 24h).
 */
const ExecutionsPerHourChart = memo(function ExecutionsPerHourChart({
  data,
  loading,
}: {
  data: ExecutionsPerHour[];
  loading: boolean;
}) {
  const maxTotal = useMemo(
    () => Math.max(...data.map((d) => d.total), 1),
    [data]
  );

  if (loading) {
    return (
      <div className="rounded-xl border border-[#2E3348] bg-[#1A1D2E]">
        <div className="border-b border-[#2E3348] px-6 py-4">
          <h3 className="text-base font-semibold text-[#F9FAFB]">Execuções por Hora (24h)</h3>
        </div>
        <div className="flex items-end gap-1 px-6 py-6">
          {Array.from({ length: 12 }).map((_, i) => (
            <Skeleton key={i} className="h-16 flex-1" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-[#2E3348] bg-[#1A1D2E]">
      <div className="border-b border-[#2E3348] px-6 py-4">
        <div className="flex items-center gap-2">
          <History className="size-4 text-[#22D3EE]" />
          <h3 className="text-base font-semibold text-[#F9FAFB]">Execuções por Hora (24h)</h3>
        </div>
      </div>

      {data.length === 0 ? (
        <div className="px-6 py-8 text-center">
          <History className="mx-auto mb-2 size-8 text-[#6B7280]" />
          <p className="text-sm text-[#9CA3AF]">Sem dados de execuções nas últimas 24h</p>
        </div>
      ) : (
        <div className="px-6 py-4">
          <div className="flex items-end gap-[2px]" style={{ height: 120 }}>
            {data.map((item) => {
              const heightPct = (item.total / maxTotal) * 100;
              const successPct = item.total > 0 ? (item.success / item.total) * 100 : 0;
              const hour = item.hour ? new Date(item.hour).getHours().toString().padStart(2, '0') : '';
              return (
                <div
                  key={item.hour}
                  className="group relative flex flex-1 flex-col items-center"
                  style={{ height: '100%' }}
                >
                  <div className="flex w-full flex-1 items-end justify-center">
                    <div
                      className="relative w-full max-w-[20px] overflow-hidden rounded-t"
                      style={{ height: `${Math.max(heightPct, 2)}%` }}
                    >
                      <div
                        className="absolute bottom-0 w-full bg-[#10B981]"
                        style={{ height: `${successPct}%` }}
                      />
                      <div
                        className="absolute top-0 w-full bg-[#EF4444]"
                        style={{ height: `${100 - successPct}%` }}
                      />
                    </div>
                  </div>
                  <span className="mt-1 text-[9px] text-[#6B7280]">{hour}h</span>
                  {/* Tooltip */}
                  <div className="pointer-events-none absolute -top-10 left-1/2 z-10 hidden -translate-x-1/2 rounded bg-[#242838] px-2 py-1 text-xs text-[#F9FAFB] shadow-lg group-hover:block">
                    {item.total} ({item.success}ok/{item.failed}err)
                  </div>
                </div>
              );
            })}
          </div>
          <div className="mt-3 flex items-center gap-4 text-xs text-[#9CA3AF]">
            <span className="flex items-center gap-1">
              <span className="inline-block size-2.5 rounded-sm bg-[#10B981]" /> Sucesso
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block size-2.5 rounded-sm bg-[#EF4444]" /> Falha
            </span>
          </div>
        </div>
      )}
    </div>
  );
});

/**
 * Gráfico horizontal de duração média por job (top 10).
 */
const DurationByJobChart = memo(function DurationByJobChart({
  data,
  loading,
}: {
  data: DurationByJob[];
  loading: boolean;
}) {
  const maxDuration = useMemo(
    () => Math.max(...data.map((d) => d.avg_duration_seconds), 1),
    [data]
  );

  if (loading) {
    return (
      <div className="rounded-xl border border-[#2E3348] bg-[#1A1D2E]">
        <div className="border-b border-[#2E3348] px-6 py-4">
          <h3 className="text-base font-semibold text-[#F9FAFB]">Duração Média por Job</h3>
        </div>
        <div className="space-y-2 px-6 py-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-8 w-full" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-[#2E3348] bg-[#1A1D2E]">
      <div className="border-b border-[#2E3348] px-6 py-4">
        <div className="flex items-center gap-2">
          <Timer className="size-4 text-[#8B5CF6]" />
          <h3 className="text-base font-semibold text-[#F9FAFB]">Duração Média por Job (7d)</h3>
        </div>
      </div>

      {data.length === 0 ? (
        <div className="px-6 py-8 text-center">
          <Timer className="mx-auto mb-2 size-8 text-[#6B7280]" />
          <p className="text-sm text-[#9CA3AF]">Sem dados de duração</p>
        </div>
      ) : (
        <div className="space-y-2 px-6 py-4">
          {data.map((item) => {
            const widthPct = (item.avg_duration_seconds / maxDuration) * 100;
            return (
              <div key={item.job_id} className="flex items-center gap-3">
                <div className="w-28 min-w-0 shrink-0">
                  <p className="truncate text-xs font-medium text-[#F9FAFB]">{item.job_name}</p>
                </div>
                <div className="flex-1">
                  <div className="h-5 w-full rounded bg-[#242838]">
                    <div
                      className="flex h-full items-center rounded bg-gradient-to-r from-[#6366F1] to-[#8B5CF6] px-2"
                      style={{ width: `${Math.max(widthPct, 3)}%` }}
                    >
                      <span className="whitespace-nowrap text-[10px] font-medium text-white">
                        {formatDuration(Math.round(item.avg_duration_seconds))}
                      </span>
                    </div>
                  </div>
                </div>
                <span className="shrink-0 text-[10px] text-[#6B7280]">
                  {item.execution_count}x
                </span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
});

/**
 * Status dos workers Celery.
 */
const WorkersStatusSection = memo(function WorkersStatusSection({
  workers,
  loading,
}: {
  workers: CeleryWorkerStatus[];
  loading: boolean;
}) {
  if (loading) {
    return (
      <div className="rounded-xl border border-[#2E3348] bg-[#1A1D2E]">
        <div className="border-b border-[#2E3348] px-6 py-4">
          <h3 className="text-base font-semibold text-[#F9FAFB]">Workers Celery</h3>
        </div>
        <div className="space-y-2 px-6 py-4">
          {Array.from({ length: 2 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-[#2E3348] bg-[#1A1D2E]">
      <div className="border-b border-[#2E3348] px-6 py-4">
        <div className="flex items-center gap-2">
          <Cpu className="size-4 text-[#10B981]" />
          <h3 className="text-base font-semibold text-[#F9FAFB]">Workers Celery</h3>
        </div>
      </div>

      {workers.length === 0 ? (
        <div className="px-6 py-6 text-center">
          <Cpu className="mx-auto mb-2 size-8 text-[#6B7280]" />
          <p className="text-sm text-[#9CA3AF]">Nenhum worker detectado</p>
        </div>
      ) : (
        <div className="divide-y divide-[#2E3348]">
          {workers.map((worker) => (
            <div key={worker.name} className="flex items-center gap-3 px-6 py-3">
              <CircleDot
                className={cn(
                  'size-3.5',
                  worker.status === 'online' ? 'text-[#10B981]' : 'text-[#EF4444]'
                )}
              />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-[#F9FAFB]">{worker.name}</p>
              </div>
              <span
                className={cn(
                  'rounded-full px-2 py-0.5 text-xs font-medium',
                  worker.status === 'online'
                    ? 'bg-[#10B981]/10 text-[#10B981]'
                    : 'bg-[#EF4444]/10 text-[#EF4444]'
                )}
              >
                {worker.status === 'online' ? 'Online' : 'Offline'}
              </span>
              {worker.active_tasks > 0 && (
                <span className="text-xs text-[#9CA3AF]">
                  {worker.active_tasks} task{worker.active_tasks !== 1 ? 's' : ''}
                </span>
              )}
            </div>
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
  const { data: opMetrics, isPending: opMetricsLoading } = useOperationalMetrics();

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

      {/* Cards operacionais extras */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        <MetricCard
          label="Tokens Hoje"
          value={opMetrics?.total_tokens_today ?? 0}
          icon={Coins}
          iconBgColor="bg-[#F59E0B]/10"
          iconColor="text-[#F59E0B]"
          loading={opMetricsLoading}
          formatValue={(v: number) => v >= 1000 ? `${(v / 1000).toFixed(1)}k` : String(v)}
        />
        <MetricCard
          label="Duração Média Hoje"
          value={opMetrics?.avg_duration_today ?? 0}
          icon={Timer}
          iconBgColor="bg-[#8B5CF6]/10"
          iconColor="text-[#8B5CF6]"
          loading={opMetricsLoading}
          formatValue={(v: number) => formatDuration(Math.round(v))}
        />
        <MetricCard
          label="Workers Online"
          value={opMetrics?.workers?.filter((w) => w.status === 'online').length ?? 0}
          icon={Cpu}
          iconBgColor="bg-[#10B981]/10"
          iconColor="text-[#10B981]"
          loading={opMetricsLoading}
        />
      </div>

      {/* Gráficos operacionais */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
        <ExecutionsPerHourChart
          data={opMetrics?.executions_per_hour ?? []}
          loading={opMetricsLoading}
        />
        <DurationByJobChart
          data={opMetrics?.duration_by_job ?? []}
          loading={opMetricsLoading}
        />
      </div>

      {/* Seções de dados */}
      <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
        {/* Últimas execuções */}
        <div className="xl:col-span-2">
          <RecentExecutionsSection
            executions={recentExecutions ?? []}
            loading={executionsLoading}
          />
        </div>

        {/* Coluna direita: workers + próximas + falhas */}
        <div className="space-y-6">
          <WorkersStatusSection
            workers={opMetrics?.workers ?? []}
            loading={opMetricsLoading}
          />

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
