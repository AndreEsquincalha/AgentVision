import { useState, useCallback, useMemo } from 'react';
import { Plus, Pencil, Trash2, Search } from 'lucide-react';
import { usePrompts, useDeletePrompt } from '@/hooks/usePrompts';
import { PageHeader } from '@/components/ui/PageHeader';
import { DataTable } from '@/components/ui/DataTable';
import type { ColumnDef } from '@/components/ui/DataTable';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { PromptForm } from '@/components/PromptForm';
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
import {
  PROMPT_CATEGORIES,
  getPromptCategoryLabel,
  DEFAULT_PAGE,
  DEFAULT_PER_PAGE,
} from '@/utils/constants';
import { truncateText, formatDateTime } from '@/utils/formatters';
import type { PromptTemplate } from '@/types';

/**
 * Página de listagem de Prompt Templates.
 * Exibe tabela paginada com filtros de busca e categoria.
 * Permite criar, editar e excluir templates.
 */
export default function PromptTemplates() {
  // --- Estado de filtros e paginação ---
  const [page, setPage] = useState(DEFAULT_PAGE);
  const [search, setSearch] = useState('');
  const [categoryFilter, setCategoryFilter] = useState<string>('all');
  const [searchInput, setSearchInput] = useState('');

  // --- Estado de dialogs ---
  const [formOpen, setFormOpen] = useState(false);
  const [editingPrompt, setEditingPrompt] = useState<PromptTemplate | null>(
    null
  );
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [promptToDelete, setPromptToDelete] = useState<PromptTemplate | null>(
    null
  );

  // --- Query e mutations ---
  const queryParams = useMemo(
    () => ({
      page,
      per_page: DEFAULT_PER_PAGE,
      search: search || undefined,
      category: categoryFilter !== 'all' ? categoryFilter : undefined,
    }),
    [page, search, categoryFilter]
  );

  const { data, isPending } = usePrompts(queryParams);
  const deleteMutation = useDeletePrompt();

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

  const handleCategoryFilterChange = useCallback((value: string) => {
    setCategoryFilter(value);
    setPage(DEFAULT_PAGE);
  }, []);

  const handleNewPrompt = useCallback(() => {
    setEditingPrompt(null);
    setFormOpen(true);
  }, []);

  const handleEditPrompt = useCallback((prompt: PromptTemplate) => {
    setEditingPrompt(prompt);
    setFormOpen(true);
  }, []);

  const handleDeleteClick = useCallback((prompt: PromptTemplate) => {
    setPromptToDelete(prompt);
    setDeleteDialogOpen(true);
  }, []);

  const handleConfirmDelete = useCallback(async () => {
    if (promptToDelete) {
      try {
        await deleteMutation.mutateAsync(promptToDelete.id);
        setDeleteDialogOpen(false);
        setPromptToDelete(null);
      } catch {
        // Erro tratado pelo hook (toast)
      }
    }
  }, [promptToDelete, deleteMutation]);

  const handlePageChange = useCallback((newPage: number) => {
    setPage(newPage);
  }, []);

  // --- Definição de colunas ---

  const columns = useMemo<ColumnDef<PromptTemplate>[]>(
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
        id: 'category',
        header: 'Categoria',
        cell: (row) => (
          <span className="text-sm text-[#9CA3AF]">
            {getPromptCategoryLabel(row.category)}
          </span>
        ),
        className: 'w-40',
      },
      {
        id: 'version',
        header: 'Versão',
        cell: (row) => (
          <span className="inline-flex items-center rounded-full bg-[#6366F1]/10 px-2.5 py-0.5 text-xs font-medium text-[#818CF8]">
            v{row.version}
          </span>
        ),
        className: 'w-24',
      },
      {
        id: 'content',
        header: 'Conteúdo',
        cell: (row) => (
          <span className="font-mono text-xs text-[#9CA3AF]">
            {truncateText(row.content, 50)}
          </span>
        ),
        className: 'hidden lg:table-cell',
      },
      {
        id: 'created_at',
        header: 'Criado em',
        cell: (row) => (
          <span className="text-sm text-[#9CA3AF]">
            {formatDateTime(row.created_at)}
          </span>
        ),
        className: 'hidden xl:table-cell w-40',
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
                    handleEditPrompt(row);
                  }}
                  className="text-[#9CA3AF] hover:bg-[#2A2F42] hover:text-white"
                  aria-label={`Editar template ${row.name}`}
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
                  aria-label={`Excluir template ${row.name}`}
                >
                  <Trash2 className="size-3.5" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>Excluir</TooltipContent>
            </Tooltip>
          </div>
        ),
        className: 'w-24',
        headerClassName: 'text-right',
      },
    ],
    [handleEditPrompt, handleDeleteClick]
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
        title="Templates de Prompt"
        description="Gerencie os templates de prompt reutilizáveis para os jobs de automação."
        action={
          <Button
            onClick={handleNewPrompt}
            className="bg-[#6366F1] text-sm font-medium text-white hover:bg-[#4F46E5]"
          >
            <Plus className="size-4" />
            Novo Template
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
            aria-label="Buscar templates por nome"
          />
        </div>

        <Select
          value={categoryFilter}
          onValueChange={handleCategoryFilterChange}
        >
          <SelectTrigger
            className="w-full border-[#2E3348] bg-[#1A1D2E] text-[#F9FAFB] focus:border-[#6366F1] focus:ring-[#6366F1] sm:w-48"
            aria-label="Filtrar por categoria"
          >
            <SelectValue placeholder="Categoria" />
          </SelectTrigger>
          <SelectContent className="border-[#2E3348] bg-[#242838]">
            <SelectItem
              value="all"
              className="text-[#F9FAFB] focus:bg-[#2A2F42] focus:text-[#F9FAFB]"
            >
              Todas as categorias
            </SelectItem>
            {PROMPT_CATEGORIES.map((cat) => (
              <SelectItem
                key={cat.value}
                value={cat.value}
                className="text-[#F9FAFB] focus:bg-[#2A2F42] focus:text-[#F9FAFB]"
              >
                {cat.label}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Tabela de templates */}
      <DataTable
        columns={columns}
        data={data?.items ?? []}
        loading={isPending}
        pagination={pagination}
        onPageChange={handlePageChange}
        rowKey={(row) => row.id}
        emptyMessage="Nenhum template encontrado"
        emptyDescription="Crie um novo template de prompt para reutilizar em seus jobs."
      />

      {/* Dialog de criação/edição */}
      <PromptForm
        open={formOpen}
        onOpenChange={setFormOpen}
        prompt={editingPrompt}
      />

      {/* Dialog de confirmação de exclusão */}
      <ConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        title="Excluir Template"
        description={`Tem certeza que deseja excluir o template "${promptToDelete?.name}"? Esta ação não pode ser desfeita.`}
        confirmLabel="Excluir"
        variant="danger"
        onConfirm={handleConfirmDelete}
        loading={deleteMutation.isPending}
      />
    </div>
  );
}
