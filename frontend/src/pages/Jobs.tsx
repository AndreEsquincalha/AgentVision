import { useState, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router';
import {
  Plus,
  Eye,
  Pencil,
  Trash2,
  Search,
  Play,
  Loader2,
} from 'lucide-react';
import { useJobs, useDeleteJob, useToggleJob, useDryRun } from '@/hooks/useJobs';
import { useProjects } from '@/hooks/useProjects';
import { PageHeader } from '@/components/ui/PageHeader';
import { DataTable } from '@/components/ui/DataTable';
import type { ColumnDef } from '@/components/ui/DataTable';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { JobForm } from '@/components/JobForm';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Switch } from '@/components/ui/switch';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { DEFAULT_PAGE, DEFAULT_PER_PAGE } from '@/utils/constants';
import { formatCronExpression, formatDateTime, truncateText } from '@/utils/formatters';
import type { Job } from '@/types';

/**
 * Pagina de listagem de jobs.
 * Exibe tabela paginada com filtros de busca, projeto e status.
 * Permite criar, editar, visualizar, excluir, ativar/desativar e dry run.
 */
export default function Jobs() {
  const navigate = useNavigate();

  // --- Estado de filtros e paginacao ---
  const [page, setPage] = useState(DEFAULT_PAGE);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [projectFilter, setProjectFilter] = useState<string>('all');
  const [searchInput, setSearchInput] = useState('');

  // --- Estado de dialogs ---
  const [formOpen, setFormOpen] = useState(false);
  const [editingJob, setEditingJob] = useState<Job | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [jobToDelete, setJobToDelete] = useState<Job | null>(null);

  // --- Estado de dry run em progresso ---
  const [dryRunJobId, setDryRunJobId] = useState<string | null>(null);

  // --- Query e mutations ---
  const queryParams = useMemo(
    () => ({
      page,
      per_page: DEFAULT_PER_PAGE,
      search: search || undefined,
      is_active:
        statusFilter === 'active'
          ? true
          : statusFilter === 'inactive'
            ? false
            : undefined,
      project_id:
        projectFilter !== 'all' ? projectFilter : undefined,
    }),
    [page, search, statusFilter, projectFilter]
  );

  const { data, isPending } = useJobs(queryParams);
  const { data: projectsData } = useProjects({ per_page: 100 });
  const deleteMutation = useDeleteJob();
  const toggleMutation = useToggleJob();
  const dryRunMutation = useDryRun();

  const projects = useMemo(
    () => projectsData?.items ?? [],
    [projectsData]
  );

  // --- Handlers ---

  const handleSearch = useCallback(() => {
    setSearch(searchInput);
    setPage(DEFAULT_PAGE);
  }, [searchInput]);

  const handleSearchKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        handleSearch();
      }
    },
    [handleSearch]
  );

  const handleStatusFilterChange = useCallback((value: string) => {
    setStatusFilter(value);
    setPage(DEFAULT_PAGE);
  }, []);

  const handleProjectFilterChange = useCallback((value: string) => {
    setProjectFilter(value);
    setPage(DEFAULT_PAGE);
  }, []);

  const handleNewJob = useCallback(() => {
    setEditingJob(null);
    setFormOpen(true);
  }, []);

  const handleEditJob = useCallback((job: Job) => {
    setEditingJob(job);
    setFormOpen(true);
  }, []);

  const handleViewJob = useCallback(
    (job: Job) => {
      navigate(`/jobs/${job.id}`);
    },
    [navigate]
  );

  const handleDeleteClick = useCallback((job: Job) => {
    setJobToDelete(job);
    setDeleteDialogOpen(true);
  }, []);

  const handleConfirmDelete = useCallback(async () => {
    if (jobToDelete) {
      try {
        await deleteMutation.mutateAsync(jobToDelete.id);
        setDeleteDialogOpen(false);
        setJobToDelete(null);
      } catch {
        // Erro tratado pelo hook (toast)
      }
    }
  }, [jobToDelete, deleteMutation]);

  const handleToggle = useCallback(
    async (job: Job, checked: boolean) => {
      try {
        await toggleMutation.mutateAsync({
          id: job.id,
          isActive: checked,
        });
      } catch {
        // Erro tratado pelo hook (toast)
      }
    },
    [toggleMutation]
  );

  const handleDryRun = useCallback(
    async (job: Job) => {
      setDryRunJobId(job.id);
      try {
        await dryRunMutation.mutateAsync(job.id);
      } catch {
        // Erro tratado pelo hook (toast)
      } finally {
        setDryRunJobId(null);
      }
    },
    [dryRunMutation]
  );

  const handlePageChange = useCallback((newPage: number) => {
    setPage(newPage);
  }, []);

  // --- Definicao de colunas ---

  const columns = useMemo<ColumnDef<Job>[]>(
    () => [
      {
        id: 'name',
        header: 'Nome',
        cell: (row) => (
          <div>
            <p className="font-medium text-[#F9FAFB]">{row.name}</p>
            {row.agent_prompt && (
              <p className="mt-0.5 text-xs text-[#6B7280]">
                {truncateText(row.agent_prompt, 60)}
              </p>
            )}
          </div>
        ),
      },
      {
        id: 'project',
        header: 'Projeto',
        cell: (row) => (
          <span className="text-sm text-[#9CA3AF]">
            {row.project_name ?? '-'}
          </span>
        ),
      },
      {
        id: 'cron',
        header: 'Agendamento',
        cell: (row) => (
          <div>
            <p className="font-mono text-xs text-[#F9FAFB]">
              {row.cron_expression}
            </p>
            <p className="mt-0.5 text-xs text-[#6B7280]">
              {formatCronExpression(row.cron_expression)}
            </p>
          </div>
        ),
      },
      {
        id: 'next_execution',
        header: 'Proxima Execucao',
        cell: (row) => (
          <span className="text-sm text-[#9CA3AF]">
            {row.next_execution ? formatDateTime(row.next_execution) : '-'}
          </span>
        ),
        className: 'hidden lg:table-cell',
      },
      {
        id: 'status',
        header: 'Status',
        cell: (row) => (
          <div
            className="flex items-center gap-2"
            onClick={(e) => e.stopPropagation()}
          >
            <Switch
              checked={row.is_active}
              onCheckedChange={(checked) => handleToggle(row, checked)}
              disabled={toggleMutation.isPending}
              aria-label={`${row.is_active ? 'Desativar' : 'Ativar'} job ${row.name}`}
              className="data-[state=checked]:bg-[#6366F1]"
            />
            <span
              className={`text-xs font-medium ${
                row.is_active ? 'text-[#10B981]' : 'text-[#6B7280]'
              }`}
            >
              {row.is_active ? 'Ativo' : 'Inativo'}
            </span>
          </div>
        ),
        className: 'w-32',
      },
      {
        id: 'actions',
        header: 'Acoes',
        cell: (row) => (
          <div className="flex items-center gap-1">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon-xs"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleViewJob(row);
                  }}
                  className="text-[#9CA3AF] hover:bg-[#2A2F42] hover:text-white"
                  aria-label={`Ver detalhes do job ${row.name}`}
                >
                  <Eye className="size-3.5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Ver detalhes</TooltipContent>
            </Tooltip>

            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon-xs"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleEditJob(row);
                  }}
                  className="text-[#9CA3AF] hover:bg-[#2A2F42] hover:text-white"
                  aria-label={`Editar job ${row.name}`}
                >
                  <Pencil className="size-3.5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Editar</TooltipContent>
            </Tooltip>

            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon-xs"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDryRun(row);
                  }}
                  disabled={dryRunJobId === row.id}
                  className="text-[#9CA3AF] hover:bg-[#22D3EE]/10 hover:text-[#22D3EE]"
                  aria-label={`Executar dry run do job ${row.name}`}
                >
                  {dryRunJobId === row.id ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : (
                    <Play className="size-3.5" />
                  )}
                </Button>
              </TooltipTrigger>
              <TooltipContent>Dry Run</TooltipContent>
            </Tooltip>

            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon-xs"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleDeleteClick(row);
                  }}
                  className="text-[#9CA3AF] hover:bg-[#EF4444]/10 hover:text-[#EF4444]"
                  aria-label={`Excluir job ${row.name}`}
                >
                  <Trash2 className="size-3.5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Excluir</TooltipContent>
            </Tooltip>
          </div>
        ),
        className: 'w-36',
        headerClassName: 'text-right',
      },
    ],
    [handleViewJob, handleEditJob, handleDeleteClick, handleToggle, handleDryRun, toggleMutation.isPending, dryRunJobId]
  );

  // --- Dados de paginacao ---

  const pagination = useMemo(
    () =>
      data
        ? {
            page: data.page,
            perPage: data.per_page,
            total: data.total,
            totalPages: data.total_pages,
          }
        : undefined,
    [data]
  );

  return (
    <div className="space-y-6">
      {/* Cabecalho */}
      <PageHeader
        title="Jobs"
        description="Gerencie os jobs de automacao e seus agendamentos."
        action={
          <Button
            onClick={handleNewJob}
            className="bg-[#6366F1] text-sm font-medium text-white hover:bg-[#4F46E5]"
          >
            <Plus className="size-4" />
            Novo Job
          </Button>
        }
      />

      {/* Filtros */}
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[#6B7280]" />
          <Input
            placeholder="Buscar por nome..."
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            onKeyDown={handleSearchKeyDown}
            onBlur={handleSearch}
            className="border-[#2E3348] bg-[#1A1D2E] pl-10 text-[#F9FAFB] placeholder-[#6B7280] focus:border-[#6366F1] focus:ring-[#6366F1]"
            aria-label="Buscar jobs por nome"
          />
        </div>

        <Select value={projectFilter} onValueChange={handleProjectFilterChange}>
          <SelectTrigger
            className="w-full border-[#2E3348] bg-[#1A1D2E] text-[#F9FAFB] focus:border-[#6366F1] focus:ring-[#6366F1] sm:w-48"
            aria-label="Filtrar por projeto"
          >
            <SelectValue placeholder="Projeto" />
          </SelectTrigger>
          <SelectContent className="border-[#2E3348] bg-[#242838]">
            <SelectItem
              value="all"
              className="text-[#F9FAFB] focus:bg-[#2A2F42] focus:text-[#F9FAFB]"
            >
              Todos os projetos
            </SelectItem>
            {projects.map((project) => (
              <SelectItem
                key={project.id}
                value={project.id}
                className="text-[#F9FAFB] focus:bg-[#2A2F42] focus:text-[#F9FAFB]"
              >
                {project.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>

        <Select value={statusFilter} onValueChange={handleStatusFilterChange}>
          <SelectTrigger
            className="w-full border-[#2E3348] bg-[#1A1D2E] text-[#F9FAFB] focus:border-[#6366F1] focus:ring-[#6366F1] sm:w-40"
            aria-label="Filtrar por status"
          >
            <SelectValue placeholder="Status" />
          </SelectTrigger>
          <SelectContent className="border-[#2E3348] bg-[#242838]">
            <SelectItem
              value="all"
              className="text-[#F9FAFB] focus:bg-[#2A2F42] focus:text-[#F9FAFB]"
            >
              Todos
            </SelectItem>
            <SelectItem
              value="active"
              className="text-[#F9FAFB] focus:bg-[#2A2F42] focus:text-[#F9FAFB]"
            >
              Ativo
            </SelectItem>
            <SelectItem
              value="inactive"
              className="text-[#F9FAFB] focus:bg-[#2A2F42] focus:text-[#F9FAFB]"
            >
              Inativo
            </SelectItem>
          </SelectContent>
        </Select>
      </div>

      {/* Tabela de jobs */}
      <DataTable
        columns={columns}
        data={data?.items ?? []}
        loading={isPending}
        pagination={pagination}
        onPageChange={handlePageChange}
        rowKey={(row) => row.id}
        emptyMessage="Nenhum job encontrado"
        emptyDescription="Crie um novo job para comecar a automatizar suas tarefas."
      />

      {/* Dialog de criacao/edicao */}
      <JobForm
        open={formOpen}
        onOpenChange={setFormOpen}
        job={editingJob}
      />

      {/* Dialog de confirmacao de exclusao */}
      <ConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        title="Excluir Job"
        description={`Tem certeza que deseja excluir o job "${jobToDelete?.name}"? Esta acao nao pode ser desfeita. Todas as execucoes associadas tambem serao removidas.`}
        confirmLabel="Excluir"
        variant="danger"
        onConfirm={handleConfirmDelete}
        loading={deleteMutation.isPending}
      />
    </div>
  );
}
