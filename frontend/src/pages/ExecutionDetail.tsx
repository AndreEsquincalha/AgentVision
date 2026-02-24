import { useState, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router';
import {
  ArrowLeft,
  Trash2,
  XCircle,
  History,
  Image,
  Eye,
  FileDown,
  Code,
  ScrollText,
  Truck,
  ChevronDown,
  ChevronUp,
  RotateCcw,
  Loader2,
  Download,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import { useExecution, useScreenshots, usePdfUrl, useRetryDelivery, useDeleteExecution } from '@/hooks/useExecutions';
import { StatusBadge } from '@/components/ui/StatusBadge';
import { DataTable } from '@/components/ui/DataTable';
import type { ColumnDef } from '@/components/ui/DataTable';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import {
  Dialog,
  DialogContent,
} from '@/components/ui/dialog';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { ROUTES, CHANNEL_TYPE_MAP } from '@/utils/constants';
import {
  formatDateTime,
  formatDateTimeFull,
  formatDuration,
} from '@/utils/formatters';
import type { DeliveryLog } from '@/types';

/**
 * Pagina de detalhes de uma execucao.
 * Exibe informacoes gerais, screenshots, PDF, dados extraidos,
 * logs de execucao e entregas com opcao de retry.
 */
export default function ExecutionDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  // --- Estado de componentes interativos ---
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const [lightboxIndex, setLightboxIndex] = useState(0);
  const [jsonExpanded, setJsonExpanded] = useState(false);
  const [logsExpanded, setLogsExpanded] = useState(false);
  const [retryingDeliveryId, setRetryingDeliveryId] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  // --- Queries ---
  const { data: execution, isPending, isError } = useExecution(id ?? '');
  const { data: screenshots, isPending: screenshotsLoading } = useScreenshots(id ?? '');
  const { data: pdfUrl } = usePdfUrl(id ?? '');

  // --- Mutations ---
  const retryMutation = useRetryDelivery();
  const deleteMutation = useDeleteExecution();

  // --- Handlers ---

  const handleBack = useCallback(() => {
    navigate(ROUTES.EXECUTIONS);
  }, [navigate]);

  const handleDeleteClick = useCallback(() => {
    setDeleteDialogOpen(true);
  }, []);

  const handleConfirmDelete = useCallback(async () => {
    if (execution) {
      try {
        await deleteMutation.mutateAsync(execution.id);
        setDeleteDialogOpen(false);
        navigate(ROUTES.EXECUTIONS);
      } catch {
        // Erro tratado pelo hook (toast)
      }
    }
  }, [execution, deleteMutation, navigate]);

  const handleOpenLightbox = useCallback((index: number) => {
    setLightboxIndex(index);
    setLightboxOpen(true);
  }, []);

  const handlePreviousScreenshot = useCallback(() => {
    setLightboxIndex((prev) =>
      prev > 0 ? prev - 1 : (screenshots?.length ?? 1) - 1
    );
  }, [screenshots]);

  const handleNextScreenshot = useCallback(() => {
    setLightboxIndex((prev) =>
      prev < (screenshots?.length ?? 1) - 1 ? prev + 1 : 0
    );
  }, [screenshots]);

  const handleToggleJson = useCallback(() => {
    setJsonExpanded((prev) => !prev);
  }, []);

  const handleToggleLogs = useCallback(() => {
    setLogsExpanded((prev) => !prev);
  }, []);

  const handleRetryDelivery = useCallback(
    async (deliveryLog: DeliveryLog) => {
      if (!id) return;
      setRetryingDeliveryId(deliveryLog.id);
      try {
        await retryMutation.mutateAsync({
          executionId: id,
          deliveryLogId: deliveryLog.id,
        });
      } catch {
        // Erro tratado pelo hook (toast)
      } finally {
        setRetryingDeliveryId(null);
      }
    },
    [id, retryMutation]
  );

  const handleDownloadPdf = useCallback(() => {
    if (pdfUrl) {
      window.open(pdfUrl, '_blank', 'noopener,noreferrer');
    }
  }, [pdfUrl]);

  // --- Dados formatados ---

  const extractedDataJson = useMemo(() => {
    if (!execution?.extracted_data) return null;
    try {
      return JSON.stringify(execution.extracted_data, null, 2);
    } catch {
      return null;
    }
  }, [execution?.extracted_data]);

  // --- Colunas da tabela de entregas ---

  const deliveryColumns = useMemo<ColumnDef<DeliveryLog>[]>(
    () => [
      {
        id: 'channel_type',
        header: 'Canal',
        cell: (row) => (
          <span className="text-sm font-medium text-[#F9FAFB]">
            {CHANNEL_TYPE_MAP[row.channel_type]}
          </span>
        ),
        className: 'w-28',
      },
      {
        id: 'status',
        header: 'Status',
        cell: (row) => (
          <StatusBadge status={row.status} variant="delivery" />
        ),
        className: 'w-32',
      },
      {
        id: 'sent_at',
        header: 'Enviado em',
        cell: (row) => (
          <span className="text-sm text-[#9CA3AF]">
            {formatDateTime(row.sent_at)}
          </span>
        ),
      },
      {
        id: 'error_message',
        header: 'Mensagem de Erro',
        cell: (row) => (
          <span className="text-sm text-[#9CA3AF]">
            {row.error_message ? (
              <span className="text-[#EF4444]" title={row.error_message}>
                {row.error_message.length > 80
                  ? `${row.error_message.substring(0, 80)}...`
                  : row.error_message}
              </span>
            ) : (
              '-'
            )}
          </span>
        ),
      },
      {
        id: 'actions',
        header: '',
        cell: (row) =>
          row.status === 'failed' ? (
            <Tooltip>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon-xs"
                  onClick={() => handleRetryDelivery(row)}
                  disabled={retryingDeliveryId === row.id}
                  className="text-[#9CA3AF] hover:bg-[#F59E0B]/10 hover:text-[#F59E0B]"
                  aria-label={`Reenviar entrega via ${CHANNEL_TYPE_MAP[row.channel_type]}`}
                >
                  {retryingDeliveryId === row.id ? (
                    <Loader2 className="size-3.5 animate-spin" />
                  ) : (
                    <RotateCcw className="size-3.5" />
                  )}
                </Button>
              </TooltipTrigger>
              <TooltipContent>Reenviar</TooltipContent>
            </Tooltip>
          ) : null,
        className: 'w-16 text-right',
        headerClassName: 'text-right',
      },
    ],
    [handleRetryDelivery, retryingDeliveryId]
  );

  // --- Loading state ---
  if (isPending) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Skeleton className="h-9 w-24" />
          <Skeleton className="h-8 w-64" />
        </div>
        <Skeleton className="h-48 w-full rounded-xl" />
        <Skeleton className="h-64 w-full rounded-xl" />
        <Skeleton className="h-48 w-full rounded-xl" />
        <Skeleton className="h-48 w-full rounded-xl" />
      </div>
    );
  }

  // --- Error / Not found state ---
  if (isError || !execution) {
    return (
      <div className="space-y-6">
        <Button
          variant="ghost"
          onClick={handleBack}
          className="text-[#9CA3AF] hover:bg-[#2A2F42] hover:text-white"
        >
          <ArrowLeft className="size-4" />
          Voltar para Execuções
        </Button>
        <div className="rounded-xl border border-[#2E3348] bg-[#1A1D2E] p-12 text-center">
          <XCircle className="mx-auto mb-3 size-10 text-[#EF4444]" />
          <h2 className="text-lg font-semibold text-[#F9FAFB]">
            Execução não encontrada
          </h2>
          <p className="mt-1 text-sm text-[#9CA3AF]">
            A execução solicitada não existe ou foi removida.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Cabecalho com botao voltar */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleBack}
            className="text-[#9CA3AF] hover:bg-[#2A2F42] hover:text-white"
            aria-label="Voltar para lista de execuções"
          >
            <ArrowLeft className="size-4" />
            Voltar
          </Button>
          <Separator orientation="vertical" className="h-6 bg-[#2E3348]" />
          <div>
            <h1 className="text-2xl font-semibold text-[#F9FAFB]">
              {execution.job_name ?? 'Execução'}
            </h1>
            <div className="mt-0.5 flex items-center gap-2">
              <StatusBadge status={execution.status} variant="execution" />
              {execution.is_dry_run && (
                <span className="inline-flex items-center rounded-full bg-[#F59E0B]/10 px-2 py-0.5 text-xs font-medium text-[#F59E0B]">
                  Dry Run
                </span>
              )}
              {execution.project_name && (
                <span className="text-xs text-[#6B7280]">
                  {execution.project_name}
                </span>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleDeleteClick}
            className="border-[#2E3348] bg-transparent text-[#EF4444] hover:bg-[#EF4444]/10 hover:text-[#EF4444]"
            aria-label="Excluir execução"
          >
            <Trash2 className="size-4" />
            Excluir
          </Button>
        </div>
      </div>

      {/* Card: Informações Gerais */}
      <div className="rounded-xl border border-[#2E3348] bg-[#1A1D2E] p-6">
        <div className="mb-4 flex items-center gap-2">
          <History className="size-5 text-[#6366F1]" />
          <h2 className="text-base font-semibold text-[#F9FAFB]">
            Informações Gerais
          </h2>
        </div>

        <div className="grid grid-cols-1 gap-x-8 gap-y-4 md:grid-cols-2">
          <InfoRow label="Job" value={execution.job_name ?? '-'} />
          <InfoRow label="Projeto" value={execution.project_name ?? '-'} />
          <InfoRow
            label="Status"
            value={
              <StatusBadge status={execution.status} variant="execution" />
            }
          />
          <InfoRow
            label="Tipo"
            value={
              <span
                className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                  execution.is_dry_run
                    ? 'bg-[#F59E0B]/10 text-[#F59E0B]'
                    : 'bg-[#6366F1]/10 text-[#6366F1]'
                }`}
              >
                {execution.is_dry_run ? 'Dry Run' : 'Produção'}
              </span>
            }
          />
          <InfoRow
            label="Início"
            value={formatDateTimeFull(execution.started_at)}
          />
          <InfoRow
            label="Fim"
            value={formatDateTimeFull(execution.finished_at)}
          />
          <InfoRow
            label="Duração"
            value={formatDuration(execution.duration_seconds)}
          />
          <InfoRow
            label="Criado em"
            value={formatDateTime(execution.created_at)}
          />
        </div>
      </div>

      {/* Secao: Screenshots */}
      <div className="rounded-xl border border-[#2E3348] bg-[#1A1D2E] p-6">
        <div className="mb-4 flex items-center gap-2">
          <Image className="size-5 text-[#8B5CF6]" />
          <h2 className="text-base font-semibold text-[#F9FAFB]">
            Screenshots
          </h2>
          {screenshots && screenshots.length > 0 && (
            <span className="text-xs text-[#6B7280]">
              ({screenshots.length} {screenshots.length === 1 ? 'imagem' : 'imagens'})
            </span>
          )}
        </div>

        {screenshotsLoading ? (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
            {Array.from({ length: 4 }, (_, i) => (
              <Skeleton key={i} className="aspect-video w-full rounded-lg" />
            ))}
          </div>
        ) : !screenshots || screenshots.length === 0 ? (
          <div className="py-8 text-center">
            <Image className="mx-auto mb-2 size-8 text-[#6B7280]" />
            <p className="text-sm text-[#9CA3AF]">
              Nenhum screenshot disponível
            </p>
            <p className="mt-1 text-xs text-[#6B7280]">
              Os screenshots aparecerão aqui após a execução ser concluída.
            </p>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 lg:grid-cols-4">
            {screenshots.map((url, index) => (
              <button
                key={index}
                onClick={() => handleOpenLightbox(index)}
                className="group relative overflow-hidden rounded-lg border border-[#2E3348] bg-[#242838] transition-all hover:border-[#6366F1] focus:outline-none focus:ring-2 focus:ring-[#6366F1]"
                aria-label={`Visualizar screenshot ${index + 1} de ${screenshots.length}`}
              >
                <img
                  src={url}
                  alt={`Screenshot ${index + 1}`}
                  className="aspect-video w-full object-cover transition-transform group-hover:scale-105"
                  loading="lazy"
                />
                <div className="absolute inset-0 flex items-center justify-center bg-black/0 transition-all group-hover:bg-black/40">
                  <Eye className="size-6 text-white opacity-0 transition-opacity group-hover:opacity-100" />
                </div>
                <span className="absolute bottom-2 right-2 rounded bg-black/60 px-1.5 py-0.5 text-xs text-white">
                  {index + 1}/{screenshots.length}
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Lightbox Dialog para screenshots */}
      <Dialog open={lightboxOpen} onOpenChange={setLightboxOpen}>
        <DialogContent
          className="max-h-[90vh] max-w-[90vw] border-[#2E3348] bg-[#1A1D2E] p-2 sm:p-4"
          showCloseButton
        >
          {screenshots && screenshots.length > 0 && (
            <div className="relative flex flex-col items-center">
              {/* Imagem */}
              <div className="flex max-h-[75vh] items-center justify-center overflow-auto">
                <img
                  src={screenshots[lightboxIndex]}
                  alt={`Screenshot ${lightboxIndex + 1}`}
                  className="max-h-[75vh] max-w-full rounded object-contain"
                />
              </div>

              {/* Navegacao */}
              {screenshots.length > 1 && (
                <div className="mt-3 flex items-center gap-4">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handlePreviousScreenshot}
                    className="border-[#2E3348] bg-transparent text-[#9CA3AF] hover:bg-[#2A2F42] hover:text-white"
                    aria-label="Screenshot anterior"
                  >
                    <ChevronLeft className="size-4" />
                    Anterior
                  </Button>
                  <span className="text-sm text-[#9CA3AF]">
                    {lightboxIndex + 1} de {screenshots.length}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleNextScreenshot}
                    className="border-[#2E3348] bg-transparent text-[#9CA3AF] hover:bg-[#2A2F42] hover:text-white"
                    aria-label="Próximo screenshot"
                  >
                    Próximo
                    <ChevronRight className="size-4" />
                  </Button>
                </div>
              )}
            </div>
          )}
        </DialogContent>
      </Dialog>

      {/* Secao: Relatório PDF */}
      <div className="rounded-xl border border-[#2E3348] bg-[#1A1D2E] p-6">
        <div className="mb-4 flex items-center gap-2">
          <FileDown className="size-5 text-[#22D3EE]" />
          <h2 className="text-base font-semibold text-[#F9FAFB]">
            Relatório PDF
          </h2>
        </div>

        {pdfUrl ? (
          <Button
            onClick={handleDownloadPdf}
            className="bg-[#6366F1] text-sm font-medium text-white hover:bg-[#4F46E5]"
          >
            <Download className="size-4" />
            Baixar Relatório PDF
          </Button>
        ) : (
          <div className="py-4 text-center">
            <FileDown className="mx-auto mb-2 size-8 text-[#6B7280]" />
            <p className="text-sm text-[#9CA3AF]">
              Nenhum relatório PDF disponível
            </p>
            <p className="mt-1 text-xs text-[#6B7280]">
              O relatório será gerado automaticamente após a análise da execução.
            </p>
          </div>
        )}
      </div>

      {/* Secao: Dados Extraídos */}
      <div className="rounded-xl border border-[#2E3348] bg-[#1A1D2E] p-6">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Code className="size-5 text-[#10B981]" />
            <h2 className="text-base font-semibold text-[#F9FAFB]">
              Dados Extraídos
            </h2>
          </div>

          {extractedDataJson && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleToggleJson}
              className="text-[#9CA3AF] hover:bg-[#2A2F42] hover:text-white"
              aria-label={jsonExpanded ? 'Recolher dados' : 'Expandir dados'}
            >
              {jsonExpanded ? (
                <>
                  <ChevronUp className="size-4" />
                  Recolher
                </>
              ) : (
                <>
                  <ChevronDown className="size-4" />
                  Expandir
                </>
              )}
            </Button>
          )}
        </div>

        {!extractedDataJson ? (
          <div className="py-4 text-center">
            <Code className="mx-auto mb-2 size-8 text-[#6B7280]" />
            <p className="text-sm text-[#9CA3AF]">
              Nenhum dado extraído disponível
            </p>
            <p className="mt-1 text-xs text-[#6B7280]">
              Os dados serão extraídos após a análise do LLM.
            </p>
          </div>
        ) : (
          <div
            className={`overflow-hidden transition-all duration-300 ${
              jsonExpanded ? 'max-h-[none]' : 'max-h-48'
            }`}
          >
            <pre className="overflow-auto rounded-lg border border-[#2E3348] bg-[#242838] p-4 font-mono text-xs leading-relaxed text-[#F9FAFB]">
              <code>{extractedDataJson}</code>
            </pre>
          </div>
        )}

        {/* Indicador de conteudo truncado */}
        {extractedDataJson && !jsonExpanded && (
          <div className="relative -mt-8 h-8 bg-gradient-to-t from-[#1A1D2E] to-transparent" />
        )}
      </div>

      {/* Secao: Logs */}
      <div className="rounded-xl border border-[#2E3348] bg-[#1A1D2E] p-6">
        <div className="mb-4 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <ScrollText className="size-5 text-[#F59E0B]" />
            <h2 className="text-base font-semibold text-[#F9FAFB]">
              Logs de Execução
            </h2>
          </div>

          {execution.logs && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleToggleLogs}
              className="text-[#9CA3AF] hover:bg-[#2A2F42] hover:text-white"
              aria-label={logsExpanded ? 'Recolher logs' : 'Expandir logs'}
            >
              {logsExpanded ? (
                <>
                  <ChevronUp className="size-4" />
                  Recolher
                </>
              ) : (
                <>
                  <ChevronDown className="size-4" />
                  Expandir
                </>
              )}
            </Button>
          )}
        </div>

        {!execution.logs ? (
          <div className="py-4 text-center">
            <ScrollText className="mx-auto mb-2 size-8 text-[#6B7280]" />
            <p className="text-sm text-[#9CA3AF]">
              Nenhum log disponível
            </p>
            <p className="mt-1 text-xs text-[#6B7280]">
              Os logs serão gerados durante a execução.
            </p>
          </div>
        ) : (
          <div
            className={`overflow-hidden transition-all duration-300 ${
              logsExpanded ? 'max-h-[none]' : 'max-h-64'
            }`}
          >
            <pre className="overflow-auto rounded-lg border border-[#2E3348] bg-[#242838] p-4 font-mono text-xs leading-relaxed text-[#F9FAFB] whitespace-pre-wrap">
              {execution.logs}
            </pre>
          </div>
        )}

        {/* Indicador de conteudo truncado */}
        {execution.logs && !logsExpanded && (
          <div className="relative -mt-8 h-8 bg-gradient-to-t from-[#1A1D2E] to-transparent" />
        )}
      </div>

      {/* Secao: Entregas */}
      <div className="rounded-xl border border-[#2E3348] bg-[#1A1D2E] p-6">
        <div className="mb-4 flex items-center gap-2">
          <Truck className="size-5 text-[#8B5CF6]" />
          <h2 className="text-base font-semibold text-[#F9FAFB]">
            Entregas
          </h2>
          {execution.delivery_logs && execution.delivery_logs.length > 0 && (
            <span className="text-xs text-[#6B7280]">
              ({execution.delivery_logs.length})
            </span>
          )}
        </div>

        {!execution.delivery_logs || execution.delivery_logs.length === 0 ? (
          <div className="py-8 text-center">
            <Truck className="mx-auto mb-2 size-8 text-[#6B7280]" />
            <p className="text-sm text-[#9CA3AF]">
              Nenhuma entrega registrada
            </p>
            <p className="mt-1 text-xs text-[#6B7280]">
              As entregas aparecerão aqui após a conclusão da execução.
            </p>
          </div>
        ) : (
          <DataTable
            columns={deliveryColumns}
            data={execution.delivery_logs}
            rowKey={(row) => row.id}
            emptyMessage="Nenhuma entrega registrada"
          />
        )}
      </div>

      {/* Dialog de confirmacao de exclusao */}
      <ConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        title="Excluir Execução"
        description="Tem certeza que deseja excluir esta execução? Esta ação não pode ser desfeita."
        confirmLabel="Excluir"
        variant="danger"
        onConfirm={handleConfirmDelete}
        loading={deleteMutation.isPending}
      />
    </div>
  );
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
