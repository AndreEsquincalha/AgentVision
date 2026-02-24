import { useState, useCallback, useMemo } from 'react';
import { useNavigate } from 'react-router';
import { Plus, Eye, Pencil, Trash2, Search, FolderKanban } from 'lucide-react';
import { useProjects, useDeleteProject } from '@/hooks/useProjects';
import { PageHeader } from '@/components/ui/PageHeader';
import { DataTable } from '@/components/ui/DataTable';
import type { ColumnDef } from '@/components/ui/DataTable';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { ProjectForm } from '@/components/ProjectForm';
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
import { LLM_PROVIDERS, DEFAULT_PAGE, DEFAULT_PER_PAGE } from '@/utils/constants';
import { truncateText, formatDateTime } from '@/utils/formatters';
import type { Project, LLMProvider } from '@/types';

/**
 * Página de listagem de projetos.
 * Exibe tabela paginada com filtros de busca e status.
 * Permite criar, editar, visualizar e excluir projetos.
 */
export default function Projects() {
  const navigate = useNavigate();

  // --- Estado de filtros e paginação ---
  const [page, setPage] = useState(DEFAULT_PAGE);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [searchInput, setSearchInput] = useState('');

  // --- Estado de dialogs ---
  const [formOpen, setFormOpen] = useState(false);
  const [editingProject, setEditingProject] = useState<Project | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [projectToDelete, setProjectToDelete] = useState<Project | null>(null);

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
    }),
    [page, search, statusFilter]
  );

  const { data, isPending } = useProjects(queryParams);
  const deleteMutation = useDeleteProject();

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

  const handleNewProject = useCallback(() => {
    setEditingProject(null);
    setFormOpen(true);
  }, []);

  const handleEditProject = useCallback((project: Project) => {
    setEditingProject(project);
    setFormOpen(true);
  }, []);

  const handleViewProject = useCallback(
    (project: Project) => {
      navigate(`/projects/${project.id}`);
    },
    [navigate]
  );

  const handleDeleteClick = useCallback((project: Project) => {
    setProjectToDelete(project);
    setDeleteDialogOpen(true);
  }, []);

  const handleConfirmDelete = useCallback(async () => {
    if (projectToDelete) {
      try {
        await deleteMutation.mutateAsync(projectToDelete.id);
        setDeleteDialogOpen(false);
        setProjectToDelete(null);
      } catch {
        // Erro tratado pelo hook (toast)
      }
    }
  }, [projectToDelete, deleteMutation]);

  const handlePageChange = useCallback((newPage: number) => {
    setPage(newPage);
  }, []);

  // --- Definição de colunas ---

  const columns = useMemo<ColumnDef<Project>[]>(
    () => [
      {
        id: 'name',
        header: 'Nome',
        cell: (row) => (
          <div>
            <p className="font-medium text-[#F9FAFB]">{row.name}</p>
            {row.description && (
              <p className="mt-0.5 text-xs text-[#6B7280]">
                {truncateText(row.description, 60)}
              </p>
            )}
          </div>
        ),
      },
      {
        id: 'base_url',
        header: 'URL',
        cell: (row) => (
          <a
            href={row.base_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-sm text-[#818CF8] hover:text-[#6366F1] hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            {truncateText(row.base_url, 40)}
          </a>
        ),
      },
      {
        id: 'llm_provider',
        header: 'Provider LLM',
        cell: (row) => (
          <span className="text-sm text-[#9CA3AF]">
            {LLM_PROVIDERS[row.llm_provider as LLMProvider] ??
              row.llm_provider}
          </span>
        ),
      },
      {
        id: 'status',
        header: 'Status',
        cell: (row) => (
          <span
            className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
              row.is_active
                ? 'bg-[#10B981]/10 text-[#10B981]'
                : 'bg-[#6B7280]/10 text-[#6B7280]'
            }`}
          >
            {row.is_active ? 'Ativo' : 'Inativo'}
          </span>
        ),
        className: 'w-24',
      },
      {
        id: 'created_at',
        header: 'Criado em',
        cell: (row) => (
          <span className="text-sm text-[#9CA3AF]">
            {formatDateTime(row.created_at)}
          </span>
        ),
        className: 'hidden lg:table-cell',
      },
      {
        id: 'actions',
        header: 'Ações',
        cell: (row) => (
          <div className="flex items-center gap-1">
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon-xs"
                  onClick={(e) => {
                    e.stopPropagation();
                    handleViewProject(row);
                  }}
                  className="text-[#9CA3AF] hover:bg-[#2A2F42] hover:text-white"
                  aria-label={`Ver detalhes do projeto ${row.name}`}
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
                    handleEditProject(row);
                  }}
                  className="text-[#9CA3AF] hover:bg-[#2A2F42] hover:text-white"
                  aria-label={`Editar projeto ${row.name}`}
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
                    handleDeleteClick(row);
                  }}
                  className="text-[#9CA3AF] hover:bg-[#EF4444]/10 hover:text-[#EF4444]"
                  aria-label={`Excluir projeto ${row.name}`}
                >
                  <Trash2 className="size-3.5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Excluir</TooltipContent>
            </Tooltip>
          </div>
        ),
        className: 'w-28',
        headerClassName: 'text-right',
      },
    ],
    [handleViewProject, handleEditProject, handleDeleteClick]
  );

  // --- Dados de paginação ---

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
      {/* Cabeçalho */}
      <PageHeader
        title="Projetos"
        description="Gerencie os projetos de automação e suas configurações."
        action={
          <Button
            onClick={handleNewProject}
            className="bg-[#6366F1] text-sm font-medium text-white hover:bg-[#4F46E5]"
          >
            <Plus className="size-4" />
            Novo Projeto
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
            aria-label="Buscar projetos por nome"
          />
        </div>

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

      {/* Tabela de projetos */}
      <DataTable
        columns={columns}
        data={data?.items ?? []}
        loading={isPending}
        pagination={pagination}
        onPageChange={handlePageChange}
        rowKey={(row) => row.id}
        emptyIcon={FolderKanban}
        emptyMessage="Nenhum projeto encontrado"
        emptyDescription="Projetos são o ponto de partida para suas automações. Crie seu primeiro projeto para começar."
        emptyAction={
          <Button
            onClick={handleNewProject}
            className="bg-[#6366F1] text-sm font-medium text-white hover:bg-[#4F46E5]"
          >
            <Plus className="size-4" />
            Criar Primeiro Projeto
          </Button>
        }
      />

      {/* Dialog de criação/edição */}
      <ProjectForm
        open={formOpen}
        onOpenChange={setFormOpen}
        project={editingProject}
      />

      {/* Dialog de confirmação de exclusão */}
      <ConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        title="Excluir Projeto"
        description={`Tem certeza que deseja excluir o projeto "${projectToDelete?.name}"? Esta ação não pode ser desfeita.`}
        confirmLabel="Excluir"
        variant="danger"
        onConfirm={handleConfirmDelete}
        loading={deleteMutation.isPending}
      />
    </div>
  );
}
