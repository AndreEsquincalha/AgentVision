import { memo, useMemo, useCallback } from 'react';
import type { ReactNode } from 'react';
import { ChevronLeft, ChevronRight, Inbox } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Skeleton } from '@/components/ui/skeleton';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

// --- Tipos ---

export interface ColumnDef<T> {
  /** Identificador da coluna */
  id: string;
  /** Título exibido no cabeçalho */
  header: string;
  /** Chave do campo no objeto de dados ou função de acesso */
  accessorKey?: keyof T;
  /** Função de renderização customizada para a célula */
  cell?: (row: T) => ReactNode;
  /** Classes CSS adicionais para a célula */
  className?: string;
  /** Classes CSS adicionais para o cabeçalho */
  headerClassName?: string;
}

export interface PaginationInfo {
  page: number;
  perPage: number;
  total: number;
  totalPages: number;
}

interface DataTableProps<T> {
  /** Definição das colunas */
  columns: ColumnDef<T>[];
  /** Dados a exibir */
  data: T[];
  /** Se a tabela está carregando dados */
  loading?: boolean;
  /** Informações de paginação */
  pagination?: PaginationInfo;
  /** Callback de mudança de página */
  onPageChange?: (page: number) => void;
  /** Mensagem para estado vazio */
  emptyMessage?: string;
  /** Descrição adicional para estado vazio */
  emptyDescription?: string;
  /** Ícone para estado vazio */
  emptyIcon?: LucideIcon;
  /** Ação call-to-action para estado vazio */
  emptyAction?: ReactNode;
  /** Número de linhas skeleton exibidas durante loading */
  skeletonRows?: number;
  /** Função para extrair key única de cada linha */
  rowKey?: (row: T) => string;
  /** Classes CSS adicionais para o container */
  className?: string;
}

/**
 * Componente de tabela reutilizável com loading state (Skeleton),
 * estado vazio e paginação integrada.
 */
function DataTableInner<T>({
  columns,
  data,
  loading = false,
  pagination,
  onPageChange,
  emptyMessage = 'Nenhum registro encontrado',
  emptyDescription,
  emptyIcon: EmptyIcon,
  emptyAction,
  skeletonRows = 5,
  rowKey,
  className,
}: DataTableProps<T>) {
  // Gera linhas de skeleton durante loading
  const skeletonArray = useMemo(
    () => Array.from({ length: skeletonRows }, (_, i) => i),
    [skeletonRows]
  );

  const handlePreviousPage = useCallback(() => {
    if (pagination && pagination.page > 1) {
      onPageChange?.(pagination.page - 1);
    }
  }, [pagination, onPageChange]);

  const handleNextPage = useCallback(() => {
    if (pagination && pagination.page < pagination.totalPages) {
      onPageChange?.(pagination.page + 1);
    }
  }, [pagination, onPageChange]);

  // Renderiza o valor da célula
  const renderCell = useCallback(
    (column: ColumnDef<T>, row: T): ReactNode => {
      if (column.cell) {
        return column.cell(row);
      }

      if (column.accessorKey) {
        const value = row[column.accessorKey];
        if (value === null || value === undefined) return '-';
        return String(value);
      }

      return '-';
    },
    []
  );

  // Ícone do empty state (fallback para Inbox)
  const ResolvedEmptyIcon = EmptyIcon ?? Inbox;

  return (
    <div
      className={cn(
        'overflow-hidden rounded-xl border border-[#2E3348] bg-[#1A1D2E]',
        className
      )}
    >
      {/* Container com scroll horizontal para responsividade mobile */}
      <div className="overflow-x-auto">
      <Table>
        {/* Cabeçalho */}
        <TableHeader>
          <TableRow className="border-b border-[#2E3348] hover:bg-transparent">
            {columns.map((column) => (
              <TableHead
                key={column.id}
                className={cn(
                  'bg-[#242838] px-6 py-3 text-xs font-medium uppercase tracking-wider text-[#9CA3AF]',
                  column.headerClassName
                )}
              >
                {column.header}
              </TableHead>
            ))}
          </TableRow>
        </TableHeader>

        {/* Corpo */}
        <TableBody>
          {/* Estado de loading */}
          {loading &&
            skeletonArray.map((index) => (
              <TableRow
                key={`skeleton-${index}`}
                className="border-b border-[#2E3348] hover:bg-transparent"
              >
                {columns.map((column) => (
                  <TableCell
                    key={`skeleton-${index}-${column.id}`}
                    className={cn('px-6 py-4', column.className)}
                  >
                    <Skeleton className="h-4 w-3/4" />
                  </TableCell>
                ))}
              </TableRow>
            ))}

          {/* Estado vazio */}
          {!loading && data.length === 0 && (
            <TableRow className="hover:bg-transparent">
              <TableCell
                colSpan={columns.length}
                className="px-6 py-16 text-center"
              >
                <div className="flex flex-col items-center gap-3">
                  <div className="rounded-full bg-[#242838] p-4">
                    <ResolvedEmptyIcon className="size-8 text-[#6B7280]" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-[#9CA3AF]">
                      {emptyMessage}
                    </p>
                    {emptyDescription && (
                      <p className="mt-1 max-w-sm text-xs text-[#6B7280]">
                        {emptyDescription}
                      </p>
                    )}
                  </div>
                  {emptyAction && (
                    <div className="mt-2">{emptyAction}</div>
                  )}
                </div>
              </TableCell>
            </TableRow>
          )}

          {/* Dados */}
          {!loading &&
            data.map((row, index) => {
              const key = rowKey ? rowKey(row) : String(index);
              return (
                <TableRow
                  key={key}
                  className="border-b border-[#2E3348] text-sm text-[#F9FAFB] transition-colors hover:bg-[#2A2F42]"
                >
                  {columns.map((column) => (
                    <TableCell
                      key={`${key}-${column.id}`}
                      className={cn('px-6 py-4', column.className)}
                    >
                      {renderCell(column, row)}
                    </TableCell>
                  ))}
                </TableRow>
              );
            })}
        </TableBody>
      </Table>
      </div>{/* Fim do overflow-x-auto */}

      {/* Paginação */}
      {pagination && pagination.totalPages > 1 && (
        <div className="flex flex-col items-center justify-between gap-3 border-t border-[#2E3348] px-4 py-3 sm:flex-row sm:px-6">
          <p className="text-xs text-[#9CA3AF]">
            Mostrando{' '}
            <span className="font-medium text-[#F9FAFB]">
              {(pagination.page - 1) * pagination.perPage + 1}
            </span>
            {' '}a{' '}
            <span className="font-medium text-[#F9FAFB]">
              {Math.min(
                pagination.page * pagination.perPage,
                pagination.total
              )}
            </span>
            {' '}de{' '}
            <span className="font-medium text-[#F9FAFB]">
              {pagination.total}
            </span>
            {' '}registros
          </p>

          <div className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={handlePreviousPage}
              disabled={pagination.page <= 1}
              className="border-[#2E3348] bg-transparent text-[#9CA3AF] hover:bg-[#2A2F42] hover:text-white disabled:opacity-50"
              aria-label="Página anterior"
            >
              <ChevronLeft className="size-4" />
              <span className="hidden sm:inline">Anterior</span>
            </Button>

            <span className="text-xs text-[#9CA3AF]">
              <span className="font-medium text-[#F9FAFB]">
                {pagination.page}
              </span>
              {' / '}
              <span className="font-medium text-[#F9FAFB]">
                {pagination.totalPages}
              </span>
            </span>

            <Button
              variant="outline"
              size="sm"
              onClick={handleNextPage}
              disabled={pagination.page >= pagination.totalPages}
              className="border-[#2E3348] bg-transparent text-[#9CA3AF] hover:bg-[#2A2F42] hover:text-white disabled:opacity-50"
              aria-label="Próxima página"
            >
              <span className="hidden sm:inline">Próximo</span>
              <ChevronRight className="size-4" />
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

export const DataTable = memo(DataTableInner) as typeof DataTableInner;
