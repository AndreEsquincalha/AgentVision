import { useState, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router';
import {
  ArrowLeft,
  Pencil,
  Trash2,
  Play,
  CalendarClock,
  FileText,
  FolderKanban,
  Mail,
  XCircle,
  Loader2,
  Settings,
  History,
} from 'lucide-react';
import {
  useJob,
  useDeleteJob,
  useToggleJob,
  useDryRun,
} from '@/hooks/useJobs';
import { JobForm } from '@/components/JobForm';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { DataTable } from '@/components/ui/DataTable';
import type { ColumnDef } from '@/components/ui/DataTable';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import { Switch } from '@/components/ui/switch';
import { ROUTES, CHANNEL_TYPE_MAP } from '@/utils/constants';
import {
  formatDateTime,
  formatCronExpression,
  formatDuration,
} from '@/utils/formatters';
import { getNextCronExecutions } from '@/utils/cronHelper';
import type { Execution } from '@/types';
import api from '@/services/api';
import { API_ENDPOINTS } from '@/utils/constants';

/**
 * Página de detalhes de um job.
 * Exibe informações gerais, configuração cron, prompt, canais de entrega
 * e últimas execuções do job.
 */
export default function JobDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  // --- Estado de dialogs ---
  const [formOpen, setFormOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [isDryRunning, setIsDryRunning] = useState(false);

  // --- Estado de paginacao das execucoes ---
  const [executionsPage, setExecutionsPage] = useState(1);

  // --- Query e mutations ---
  const { data: job, isPending, isError } = useJob(id ?? '');
  const deleteMutation = useDeleteJob();
  const toggleMutation = useToggleJob();
  const dryRunMutation = useDryRun();

  // Busca execucoes do job via query direta
  const { data: executionsData, isPending: executionsLoading } = useJobExecutions(
    id ?? '',
    executionsPage
  );

  // Proximas execucoes baseadas na expressao cron
  const nextExecutions = useMemo(
    () => (job ? getNextCronExecutions(job.cron_expression, 5) : []),
    [job]
  );

  // --- Handlers ---

  const handleBack = useCallback(() => {
    navigate(ROUTES.JOBS);
  }, [navigate]);

  const handleEdit = useCallback(() => {
    setFormOpen(true);
  }, []);

  const handleDeleteClick = useCallback(() => {
    setDeleteDialogOpen(true);
  }, []);

  const handleConfirmDelete = useCallback(async () => {
    if (job) {
      try {
        await deleteMutation.mutateAsync(job.id);
        setDeleteDialogOpen(false);
        navigate(ROUTES.JOBS);
      } catch {
        // Erro tratado pelo hook (toast)
      }
    }
  }, [job, deleteMutation, navigate]);

  const handleToggle = useCallback(
    async (checked: boolean) => {
      if (job) {
        try {
          await toggleMutation.mutateAsync({
            id: job.id,
            isActive: checked,
          });
        } catch {
          // Erro tratado pelo hook (toast)
        }
      }
    },
    [job, toggleMutation]
  );

  const handleDryRun = useCallback(async () => {
    if (job) {
      setIsDryRunning(true);
      try {
        await dryRunMutation.mutateAsync(job.id);
      } catch {
        // Erro tratado pelo hook (toast)
      } finally {
        setIsDryRunning(false);
      }
    }
  }, [job, dryRunMutation]);

  const handleExecutionsPageChange = useCallback((newPage: number) => {
    setExecutionsPage(newPage);
  }, []);

  const handleViewExecution = useCallback(
    (execution: Execution) => {
      navigate(`/executions/${execution.id}`);
    },
    [navigate]
  );

  // --- Colunas da tabela de execucoes ---

  const executionColumns = useMemo<ColumnDef<Execution>[]>(
    () => [
      {
        id: 'status',
        header: 'Status',
        cell: (row) => (
          <StatusBadge status={row.status} variant="execution" />
        ),
        className: 'w-32',
      },
      {
        id: 'started_at',
        header: 'Iniciado em',
        cell: (row) => (
          <span className="text-sm text-[#9CA3AF]">
            {formatDateTime(row.started_at)}
          </span>
        ),
      },
      {
        id: 'duration',
        header: 'Duração',
        cell: (row) => (
          <span className="text-sm text-[#9CA3AF]">
            {formatDuration(row.duration_seconds)}
          </span>
        ),
      },
      {
        id: 'is_dry_run',
        header: 'Tipo',
        cell: (row) => (
          <span
            className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
              row.is_dry_run
                ? 'bg-[#F59E0B]/10 text-[#F59E0B]'
                : 'bg-[#6366F1]/10 text-[#6366F1]'
            }`}
          >
            {row.is_dry_run ? 'Dry Run' : 'Produção'}
          </span>
        ),
        className: 'w-28',
      },
      {
        id: 'actions',
        header: '',
        cell: (row) => (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => handleViewExecution(row)}
            className="text-[#9CA3AF] hover:bg-[#2A2F42] hover:text-white"
          >
            Ver detalhes
          </Button>
        ),
        className: 'w-32 text-right',
        headerClassName: 'text-right',
      },
    ],
    [handleViewExecution]
  );

  const executionsPagination = useMemo(
    () =>
      executionsData
        ? {
            page: executionsData.page,
            perPage: executionsData.per_page,
            total: executionsData.total,
            totalPages: executionsData.total_pages,
          }
        : undefined,
    [executionsData]
  );

  // --- Loading state ---
  if (isPending) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Skeleton className="h-9 w-24" />
          <Skeleton className="h-8 w-64" />
        </div>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Skeleton className="h-64 w-full rounded-xl" />
          <Skeleton className="h-64 w-full rounded-xl" />
        </div>
        <Skeleton className="h-48 w-full rounded-xl" />
        <Skeleton className="h-64 w-full rounded-xl" />
      </div>
    );
  }

  // --- Error / Not found state ---
  if (isError || !job) {
    return (
      <div className="space-y-6">
        <Button
          variant="ghost"
          onClick={handleBack}
          className="text-[#9CA3AF] hover:bg-[#2A2F42] hover:text-white"
        >
          <ArrowLeft className="size-4" />
          Voltar para Jobs
        </Button>
        <div className="rounded-xl border border-[#2E3348] bg-[#1A1D2E] p-12 text-center">
          <XCircle className="mx-auto mb-3 size-10 text-[#EF4444]" />
          <h2 className="text-lg font-semibold text-[#F9FAFB]">
            Job não encontrado
          </h2>
          <p className="mt-1 text-sm text-[#9CA3AF]">
            O job solicitado não existe ou foi removido.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Cabecalho com botao voltar e acoes */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleBack}
            className="text-[#9CA3AF] hover:bg-[#2A2F42] hover:text-white"
            aria-label="Voltar para lista de jobs"
          >
            <ArrowLeft className="size-4" />
            Voltar
          </Button>
          <Separator orientation="vertical" className="h-6 bg-[#2E3348]" />
          <div>
            <h1 className="text-2xl font-semibold text-[#F9FAFB]">
              {job.name}
            </h1>
            <div className="mt-0.5 flex items-center gap-2">
              <span
                className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                  job.is_active
                    ? 'bg-[#10B981]/10 text-[#10B981]'
                    : 'bg-[#6B7280]/10 text-[#6B7280]'
                }`}
              >
                {job.is_active ? 'Ativo' : 'Inativo'}
              </span>
              {job.project_name && (
                <span className="text-xs text-[#6B7280]">
                  {job.project_name}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Toggle ativo/inativo */}
          <div className="flex items-center gap-2 rounded-lg border border-[#2E3348] bg-[#242838] px-3 py-1.5">
            <Switch
              checked={job.is_active}
              onCheckedChange={handleToggle}
              disabled={toggleMutation.isPending}
              aria-label={`${job.is_active ? 'Desativar' : 'Ativar'} job`}
              className="data-[state=checked]:bg-[#6366F1]"
            />
            <span className="text-xs text-[#9CA3AF]">
              {job.is_active ? 'Ativo' : 'Inativo'}
            </span>
          </div>

          <Button
            variant="outline"
            size="sm"
            onClick={handleDryRun}
            disabled={isDryRunning}
            className="border-[#2E3348] bg-transparent text-[#22D3EE] hover:bg-[#22D3EE]/10 hover:text-[#22D3EE]"
          >
            {isDryRunning ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <Play className="size-4" />
            )}
            Dry Run
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={handleEdit}
            className="border-[#2E3348] bg-transparent text-[#9CA3AF] hover:bg-[#2A2F42] hover:text-white"
          >
            <Pencil className="size-4" />
            Editar
          </Button>

          <Button
            variant="outline"
            size="sm"
            onClick={handleDeleteClick}
            className="border-[#2E3348] bg-transparent text-[#EF4444] hover:bg-[#EF4444]/10 hover:text-[#EF4444]"
          >
            <Trash2 className="size-4" />
            Excluir
          </Button>
        </div>
      </div>

      {/* Cards de informacoes */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Card: Informações Gerais */}
        <div className="rounded-xl border border-[#2E3348] bg-[#1A1D2E] p-6">
          <div className="mb-4 flex items-center gap-2">
            <FolderKanban className="size-5 text-[#6366F1]" />
            <h2 className="text-base font-semibold text-[#F9FAFB]">
              Informações Gerais
            </h2>
          </div>

          <div className="space-y-4">
            <InfoRow label="Nome" value={job.name} />
            <InfoRow
              label="Projeto"
              value={job.project_name ?? '-'}
            />
            <InfoRow
              label="Notificar em falha"
              value={
                <span
                  className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                    job.notify_on_failure
                      ? 'bg-[#10B981]/10 text-[#10B981]'
                      : 'bg-[#6B7280]/10 text-[#6B7280]'
                  }`}
                >
                  {job.notify_on_failure ? 'Sim' : 'Nao'}
                </span>
              }
            />
            <InfoRow
              label="Criado em"
              value={formatDateTime(job.created_at)}
            />
            <InfoRow
              label="Atualizado em"
              value={formatDateTime(job.updated_at)}
            />
          </div>
        </div>

        {/* Card: Agendamento Cron */}
        <div className="rounded-xl border border-[#2E3348] bg-[#1A1D2E] p-6">
          <div className="mb-4 flex items-center gap-2">
            <CalendarClock className="size-5 text-[#8B5CF6]" />
            <h2 className="text-base font-semibold text-[#F9FAFB]">
              Agendamento
            </h2>
          </div>

          <div className="space-y-4">
            <InfoRow
              label="Expressão Cron"
              value={
                <code className="rounded bg-[#242838] px-2 py-0.5 font-mono text-xs text-[#F9FAFB]">
                  {job.cron_expression}
                </code>
              }
            />
            <InfoRow
              label="Descrição"
              value={formatCronExpression(job.cron_expression)}
            />
            <InfoRow
              label="Próxima execução"
              value={
                job.next_execution
                  ? formatDateTime(job.next_execution)
                  : nextExecutions[0]
                    ? formatDateTime(nextExecutions[0])
                    : '-'
              }
            />
          </div>

          {/* Lista de proximas execucoes */}
          {nextExecutions.length > 0 && (
            <div className="mt-4 rounded-lg border border-[#2E3348] bg-[#242838] p-3">
              <p className="mb-2 text-xs font-medium text-[#9CA3AF]">
                Próximas execuções agendadas
              </p>
              <ul className="space-y-1">
                {nextExecutions.map((date, index) => (
                  <li
                    key={index}
                    className="text-xs text-[#F9FAFB]"
                  >
                    {formatDateTime(date)}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </div>

      {/* Card: Prompt do agente */}
      <div className="rounded-xl border border-[#2E3348] bg-[#1A1D2E] p-6">
        <div className="mb-4 flex items-center gap-2">
          <FileText className="size-5 text-[#22D3EE]" />
          <h2 className="text-base font-semibold text-[#F9FAFB]">
            Prompt do Agente
          </h2>
        </div>

        <div className="rounded-lg border border-[#2E3348] bg-[#242838] p-4">
          <p className="whitespace-pre-wrap text-sm leading-relaxed text-[#F9FAFB]">
            {job.agent_prompt}
          </p>
        </div>

        {job.execution_params &&
          Object.keys(job.execution_params).length > 0 && (
            <div className="mt-4">
              <p className="mb-2 text-xs font-medium text-[#9CA3AF]">
                Parâmetros de Execução
              </p>
              <pre className="overflow-auto rounded-lg border border-[#2E3348] bg-[#242838] p-3 font-mono text-xs text-[#F9FAFB]">
                {JSON.stringify(job.execution_params, null, 2)}
              </pre>
            </div>
          )}
      </div>

      {/* Card: Canais de entrega */}
      <div className="rounded-xl border border-[#2E3348] bg-[#1A1D2E] p-6">
        <div className="mb-4 flex items-center gap-2">
          <Mail className="size-5 text-[#F59E0B]" />
          <h2 className="text-base font-semibold text-[#F9FAFB]">
            Canais de Entrega
          </h2>
        </div>

        {(!job.delivery_configs || job.delivery_configs.length === 0) ? (
          <div className="py-6 text-center">
            <Settings className="mx-auto mb-2 size-8 text-[#6B7280]" />
            <p className="text-sm text-[#9CA3AF]">
              Nenhum canal de entrega configurado
            </p>
            <p className="mt-1 text-xs text-[#6B7280]">
              Edite o job para adicionar canais de entrega.
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {job.delivery_configs.map((config) => (
              <div
                key={config.id}
                className="flex items-center justify-between rounded-lg border border-[#2E3348] bg-[#242838] p-4"
              >
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-[#F9FAFB]">
                      {CHANNEL_TYPE_MAP[config.channel_type]}
                    </span>
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                        config.is_active
                          ? 'bg-[#10B981]/10 text-[#10B981]'
                          : 'bg-[#6B7280]/10 text-[#6B7280]'
                      }`}
                    >
                      {config.is_active ? 'Ativo' : 'Inativo'}
                    </span>
                  </div>
                  <p className="text-xs text-[#9CA3AF]">
                    {config.recipients.join(', ')}
                  </p>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Card: Ultimas execucoes */}
      <div className="rounded-xl border border-[#2E3348] bg-[#1A1D2E] p-6">
        <div className="mb-4 flex items-center gap-2">
          <History className="size-5 text-[#10B981]" />
          <h2 className="text-base font-semibold text-[#F9FAFB]">
            Últimas Execuções
          </h2>
        </div>

        <DataTable
          columns={executionColumns}
          data={executionsData?.items ?? []}
          loading={executionsLoading}
          pagination={executionsPagination}
          onPageChange={handleExecutionsPageChange}
          rowKey={(row) => row.id}
          emptyMessage="Nenhuma execução encontrada"
          emptyDescription="As execuções deste job aparecerão aqui."
          skeletonRows={3}
        />
      </div>

      {/* Dialog de edicao */}
      <JobForm
        open={formOpen}
        onOpenChange={setFormOpen}
        job={job}
      />

      {/* Dialog de confirmacao de exclusao */}
      <ConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        title="Excluir Job"
        description={`Tem certeza que deseja excluir o job "${job.name}"? Esta ação não pode ser desfeita. Todas as execuções associadas também serão removidas.`}
        confirmLabel="Excluir"
        variant="danger"
        onConfirm={handleConfirmDelete}
        loading={deleteMutation.isPending}
      />
    </div>
  );
}

// --- Hook auxiliar: busca execucoes de um job ---

import { useQuery } from '@tanstack/react-query';
import type { PaginatedResponse } from '@/types';

function useJobExecutions(jobId: string, page: number = 1) {
  return useQuery<PaginatedResponse<Execution>>({
    queryKey: ['executions', 'by-job', jobId, { page }],
    queryFn: async () => {
      const response = await api.get<PaginatedResponse<Execution>>(
        API_ENDPOINTS.EXECUTIONS.LIST,
        { params: { job_id: jobId, page, per_page: 10 } }
      );
      return response.data;
    },
    enabled: !!jobId,
  });
}

// --- Componente auxiliar: Linha de informacao ---

interface InfoRowProps {
  label: string;
  value: React.ReactNode;
  muted?: boolean;
}

function InfoRow({ label, value, muted = false }: InfoRowProps) {
  return (
    <div className="flex items-start justify-between gap-4">
      <span className="shrink-0 text-sm text-[#9CA3AF]">{label}</span>
      <span
        className={`text-right text-sm ${
          muted ? 'text-[#6B7280]' : 'text-[#F9FAFB]'
        }`}
      >
        {value}
      </span>
    </div>
  );
}
