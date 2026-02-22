import { useState, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router';
import {
  Eye,
  Filter,
} from 'lucide-react';
import { useExecutions } from '@/hooks/useExecutions';
import { useProjects } from '@/hooks/useProjects';
import { useJobs } from '@/hooks/useJobs';
import { PageHeader } from '@/components/ui/PageHeader';
import { DataTable } from '@/components/ui/DataTable';
import type { ColumnDef } from '@/components/ui/DataTable';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
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
import { formatDateTime, formatDuration } from '@/utils/formatters';
import type { Execution, ExecutionStatus } from '@/types';

/**
 * Pagina de listagem de execucoes.
 * Exibe tabela paginada com filtros de projeto, job, status e intervalo de datas.
 * Execucoes sao criadas automaticamente pelos jobs — nao ha botao de criar.
 */
export default function Executions() {
  const navigate = useNavigate();

  // --- Estado de filtros e paginacao ---
  const [page, setPage] = useState(DEFAULT_PAGE);
  const [projectFilter, setProjectFilter] = useState<string>('all');
  const [jobFilter, setJobFilter] = useState<string>('all');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [dateFrom, setDateFrom] = useState<string>('');
  const [dateTo, setDateTo] = useState<string>('');

  // --- Controle de visibilidade dos filtros avancados ---
  const [showAdvancedFilters, setShowAdvancedFilters] = useState(false);

  // --- Query params ---
  const queryParams = useMemo(
    () => ({
      page,
      per_page: DEFAULT_PER_PAGE,
      project_id: projectFilter !== 'all' ? projectFilter : undefined,
      job_id: jobFilter !== 'all' ? jobFilter : undefined,
      status:
        statusFilter !== 'all'
          ? (statusFilter as ExecutionStatus)
          : undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    }),
    [page, projectFilter, jobFilter, statusFilter, dateFrom, dateTo]
  );

  const { data, isPending } = useExecutions(queryParams);

  // Busca projetos e jobs para os selects de filtro
  const { data: projectsData } = useProjects({ per_page: 100 });
  const { data: jobsData } = useJobs({ per_page: 100 });

  const projects = useMemo(
    () => projectsData?.items ?? [],
    [projectsData]
  );

  const jobs = useMemo(
    () => jobsData?.items ?? [],
    [jobsData]
  );

  // Filtra jobs pelo projeto selecionado
  const filteredJobs = useMemo(
    () =>
      projectFilter !== 'all'
        ? jobs.filter((job) => job.project_id === projectFilter)
        : jobs,
    [jobs, projectFilter]
  );

  // --- Handlers ---

  const handleProjectFilterChange = useCallback(
    (value: string) => {
      setProjectFilter(value);
      // Limpa filtro de job quando muda o projeto
      setJobFilter('all');
      setPage(DEFAULT_PAGE);
    },
    []
  );

  const handleJobFilterChange = useCallback((value: string) => {
    setJobFilter(value);
    setPage(DEFAULT_PAGE);
  }, []);

  const handleStatusFilterChange = useCallback((value: string) => {
    setStatusFilter(value);
    setPage(DEFAULT_PAGE);
  }, []);

  const handleDateFromChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setDateFrom(e.target.value);
      setPage(DEFAULT_PAGE);
    },
    []
  );

  const handleDateToChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      setDateTo(e.target.value);
      setPage(DEFAULT_PAGE);
    },
    []
  );

  const handleToggleAdvancedFilters = useCallback(() => {
    setShowAdvancedFilters((prev) => !prev);
  }, []);

  const handleClearFilters = useCallback(() => {
    setProjectFilter('all');
    setJobFilter('all');
    setStatusFilter('all');
    setDateFrom('');
    setDateTo('');
    setPage(DEFAULT_PAGE);
  }, []);

  const handleViewExecution = useCallback(
    (execution: Execution) => {
      navigate(`/executions/${execution.id}`);
    },
    [navigate]
  );

  const handlePageChange = useCallback((newPage: number) => {
    setPage(newPage);
  }, []);

  // Verifica se ha filtros ativos
  const hasActiveFilters = useMemo(
    () =>
      projectFilter !== 'all' ||
      jobFilter !== 'all' ||
      statusFilter !== 'all' ||
      dateFrom !== '' ||
      dateTo !== '',
    [projectFilter, jobFilter, statusFilter, dateFrom, dateTo]
  );

  // --- Definicao de colunas ---

  const columns = useMemo<ColumnDef<Execution>[]>(
    () => [
      {
        id: 'job_name',
        header: 'Job',
        cell: (row) => (
          <div>
            <p className="font-medium text-[#F9FAFB]">
              {row.job_name ?? '-'}
            </p>
          </div>
        ),
      },
      {
        id: 'project_name',
        header: 'Projeto',
        cell: (row) => (
          <span className="text-sm text-[#9CA3AF]">
            {row.project_name ?? '-'}
          </span>
        ),
        className: 'hidden md:table-cell',
      },
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
        className: 'hidden lg:table-cell',
      },
      {
        id: 'duration',
        header: 'Duracao',
        cell: (row) => (
          <span className="text-sm text-[#9CA3AF]">
            {formatDuration(row.duration_seconds)}
          </span>
        ),
        className: 'hidden lg:table-cell w-24',
      },
      {
        id: 'type',
        header: 'Tipo',
        cell: (row) => (
          <span
            className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
              row.is_dry_run
                ? 'bg-[#F59E0B]/10 text-[#F59E0B]'
                : 'bg-[#6366F1]/10 text-[#6366F1]'
            }`}
          >
            {row.is_dry_run ? 'Dry Run' : 'Producao'}
          </span>
        ),
        className: 'w-28 hidden sm:table-cell',
      },
      {
        id: 'actions',
        header: '',
        cell: (row) => (
          <div className="flex items-center justify-end">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon-xs"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleViewExecution(row);
                  }}
                  className="text-[#9CA3AF] hover:bg-[#2A2F42] hover:text-white"
                  aria-label={`Ver detalhes da execucao ${row.job_name ?? row.id}`}
                >
                  <Eye className="size-3.5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Ver detalhes</TooltipContent>
            </Tooltip>
          </div>
        ),
        className: 'w-16',
        headerClassName: 'text-right',
      },
    ],
    [handleViewExecution]
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
        title="Execucoes"
        description="Historico de execucoes dos jobs de automacao."
      />

      {/* Filtros principais */}
      <div className="space-y-3">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          {/* Filtro de projeto */}
          <Select
            value={projectFilter}
            onValueChange={handleProjectFilterChange}
          >
            <SelectTrigger
              className="w-full border-[#2E3348] bg-[#1A1D2E] text-[#F9FAFB] focus:border-[#6366F1] focus:ring-[#6366F1] sm:w-52"
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

          {/* Filtro de job */}
          <Select value={jobFilter} onValueChange={handleJobFilterChange}>
            <SelectTrigger
              className="w-full border-[#2E3348] bg-[#1A1D2E] text-[#F9FAFB] focus:border-[#6366F1] focus:ring-[#6366F1] sm:w-52"
              aria-label="Filtrar por job"
            >
              <SelectValue placeholder="Job" />
            </SelectTrigger>
            <SelectContent className="border-[#2E3348] bg-[#242838]">
              <SelectItem
                value="all"
                className="text-[#F9FAFB] focus:bg-[#2A2F42] focus:text-[#F9FAFB]"
              >
                Todos os jobs
              </SelectItem>
              {filteredJobs.map((job) => (
                <SelectItem
                  key={job.id}
                  value={job.id}
                  className="text-[#F9FAFB] focus:bg-[#2A2F42] focus:text-[#F9FAFB]"
                >
                  {job.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>

          {/* Filtro de status */}
          <Select
            value={statusFilter}
            onValueChange={handleStatusFilterChange}
          >
            <SelectTrigger
              className="w-full border-[#2E3348] bg-[#1A1D2E] text-[#F9FAFB] focus:border-[#6366F1] focus:ring-[#6366F1] sm:w-44"
              aria-label="Filtrar por status"
            >
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent className="border-[#2E3348] bg-[#242838]">
              <SelectItem
                value="all"
                className="text-[#F9FAFB] focus:bg-[#2A2F42] focus:text-[#F9FAFB]"
              >
                Todos os status
              </SelectItem>
              <SelectItem
                value="pending"
                className="text-[#F9FAFB] focus:bg-[#2A2F42] focus:text-[#F9FAFB]"
              >
                Pendente
              </SelectItem>
              <SelectItem
                value="running"
                className="text-[#F9FAFB] focus:bg-[#2A2F42] focus:text-[#F9FAFB]"
              >
                Em andamento
              </SelectItem>
              <SelectItem
                value="success"
                className="text-[#F9FAFB] focus:bg-[#2A2F42] focus:text-[#F9FAFB]"
              >
                Sucesso
              </SelectItem>
              <SelectItem
                value="failed"
                className="text-[#F9FAFB] focus:bg-[#2A2F42] focus:text-[#F9FAFB]"
              >
                Falha
              </SelectItem>
            </SelectContent>
          </Select>

          {/* Botao filtros avancados */}
          <Button
            variant="outline"
            size="sm"
            onClick={handleToggleAdvancedFilters}
            className={`border-[#2E3348] bg-transparent text-[#9CA3AF] hover:bg-[#2A2F42] hover:text-white ${
              showAdvancedFilters ? 'border-[#6366F1] text-[#6366F1]' : ''
            }`}
          >
            <Filter className="size-4" />
            Datas
          </Button>

          {/* Botao limpar filtros */}
          {hasActiveFilters && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleClearFilters}
              className="text-[#9CA3AF] hover:bg-[#2A2F42] hover:text-white"
            >
              Limpar filtros
            </Button>
          )}
        </div>

        {/* Filtros de data (visivel quando ativado) */}
        {showAdvancedFilters && (
          <div className="flex flex-col gap-3 rounded-lg border border-[#2E3348] bg-[#242838] p-4 sm:flex-row sm:items-center">
            <div className="flex items-center gap-2">
              <label
                htmlFor="date-from"
                className="shrink-0 text-sm text-[#9CA3AF]"
              >
                De:
              </label>
              <Input
                id="date-from"
                type="date"
                value={dateFrom}
                onChange={handleDateFromChange}
                className="w-full border-[#2E3348] bg-[#1A1D2E] text-[#F9FAFB] focus:border-[#6366F1] focus:ring-[#6366F1] sm:w-44 [&::-webkit-calendar-picker-indicator]:invert"
                aria-label="Data inicial"
              />
            </div>
            <div className="flex items-center gap-2">
              <label
                htmlFor="date-to"
                className="shrink-0 text-sm text-[#9CA3AF]"
              >
                Ate:
              </label>
              <Input
                id="date-to"
                type="date"
                value={dateTo}
                onChange={handleDateToChange}
                className="w-full border-[#2E3348] bg-[#1A1D2E] text-[#F9FAFB] focus:border-[#6366F1] focus:ring-[#6366F1] sm:w-44 [&::-webkit-calendar-picker-indicator]:invert"
                aria-label="Data final"
              />
            </div>
          </div>
        )}
      </div>

      {/* Tabela de execucoes */}
      <DataTable
        columns={columns}
        data={data?.items ?? []}
        loading={isPending}
        pagination={pagination}
        onPageChange={handlePageChange}
        rowKey={(row) => row.id}
        emptyMessage="Nenhuma execucao encontrada"
        emptyDescription="As execucoes dos seus jobs aparecerao aqui quando forem executados."
      />
    </div>
  );
}
