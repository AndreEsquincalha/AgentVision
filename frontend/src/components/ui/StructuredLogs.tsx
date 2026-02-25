import { memo, useState, useMemo, useCallback } from 'react';
import {
  ChevronDown,
  ChevronUp,
  ScrollText,
  AlertTriangle,
  XCircle,
  Info,
  ChevronRight,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import type { StructuredLogEntry, LogLevel, LogPhase } from '@/types';

// --- Mapeamento de cores por nivel de log ---

interface LogLevelStyle {
  /** Classe CSS para o texto */
  textColor: string;
  /** Classe CSS para o fundo do badge */
  badgeBg: string;
  /** Classe CSS para o texto do badge */
  badgeText: string;
  /** Icone do nivel */
  icon: React.ComponentType<{ className?: string }>;
  /** Se o texto deve ser negrito */
  bold: boolean;
}

const LOG_LEVEL_STYLES: Record<LogLevel, LogLevelStyle> = {
  INFO: {
    textColor: 'text-[#9CA3AF]',
    badgeBg: 'bg-[#6B7280]/10',
    badgeText: 'text-[#9CA3AF]',
    icon: Info,
    bold: false,
  },
  WARNING: {
    textColor: 'text-[#F59E0B]',
    badgeBg: 'bg-[#F59E0B]/10',
    badgeText: 'text-[#F59E0B]',
    icon: AlertTriangle,
    bold: false,
  },
  ERROR: {
    textColor: 'text-[#EF4444]',
    badgeBg: 'bg-[#EF4444]/10',
    badgeText: 'text-[#EF4444]',
    icon: XCircle,
    bold: false,
  },
  FATAL: {
    textColor: 'text-[#EF4444]',
    badgeBg: 'bg-[#EF4444]/20',
    badgeText: 'text-[#EF4444]',
    icon: XCircle,
    bold: true,
  },
};

// --- Mapeamento de rotulos de fase ---

const PHASE_LABELS: Record<LogPhase, string> = {
  browser: 'Navegador',
  screenshots: 'Screenshots',
  analysis: 'Analise IA',
  pdf: 'PDF',
  delivery: 'Entrega',
};

const PHASE_COLORS: Record<LogPhase, string> = {
  browser: 'bg-[#6366F1]/10 text-[#818CF8]',
  screenshots: 'bg-[#8B5CF6]/10 text-[#A78BFA]',
  analysis: 'bg-[#22D3EE]/10 text-[#22D3EE]',
  pdf: 'bg-[#10B981]/10 text-[#10B981]',
  delivery: 'bg-[#F59E0B]/10 text-[#F59E0B]',
};

// --- Funcao auxiliar para formatar timestamp ---

/**
 * Extrai HH:MM:SS de um timestamp ISO ou formatado.
 */
function formatTimestamp(timestamp: string): string {
  try {
    const date = new Date(timestamp);
    if (isNaN(date.getTime())) {
      // Tenta extrair HH:MM:SS direto da string
      const match = timestamp.match(/(\d{2}:\d{2}:\d{2})/);
      return match ? match[1] : timestamp;
    }
    return date.toLocaleTimeString('pt-BR', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch {
    return timestamp;
  }
}

// --- Componente: Entrada individual de log ---

interface LogEntryRowProps {
  entry: StructuredLogEntry;
}

const LogEntryRow = memo(function LogEntryRow({ entry }: LogEntryRowProps) {
  const [metadataOpen, setMetadataOpen] = useState(false);
  const style = LOG_LEVEL_STYLES[entry.level] ?? LOG_LEVEL_STYLES.INFO;
  const LevelIcon = style.icon;
  const hasMetadata =
    entry.metadata !== null &&
    entry.metadata !== undefined &&
    Object.keys(entry.metadata).length > 0;

  const handleToggleMetadata = useCallback(() => {
    setMetadataOpen((prev) => !prev);
  }, []);

  return (
    <div className="group">
      <div className="flex items-start gap-2 px-3 py-1.5 hover:bg-[#2A2F42]/50">
        {/* Timestamp */}
        <span className="shrink-0 font-mono text-[11px] leading-5 text-[#6B7280]">
          {formatTimestamp(entry.timestamp)}
        </span>

        {/* Badge de nivel */}
        <span
          className={`inline-flex shrink-0 items-center gap-1 rounded px-1.5 py-0.5 text-[10px] font-medium uppercase ${style.badgeBg} ${style.badgeText}`}
        >
          <LevelIcon className="size-3" />
          {entry.level}
        </span>

        {/* Badge de fase */}
        <span
          className={`inline-flex shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium ${PHASE_COLORS[entry.phase] ?? 'bg-[#6B7280]/10 text-[#9CA3AF]'}`}
        >
          {PHASE_LABELS[entry.phase] ?? entry.phase}
        </span>

        {/* Mensagem */}
        <span
          className={`flex-1 text-xs leading-5 ${style.textColor} ${style.bold ? 'font-semibold' : ''}`}
        >
          {entry.message}
        </span>

        {/* Botao de metadata */}
        {hasMetadata && (
          <button
            type="button"
            onClick={handleToggleMetadata}
            className="shrink-0 rounded p-0.5 text-[#6B7280] transition-colors hover:bg-[#2A2F42] hover:text-[#9CA3AF]"
            aria-label={metadataOpen ? 'Ocultar metadados' : 'Exibir metadados'}
          >
            <ChevronRight
              className={`size-3.5 transition-transform ${metadataOpen ? 'rotate-90' : ''}`}
            />
          </button>
        )}
      </div>

      {/* Metadados expandidos */}
      {hasMetadata && metadataOpen && (
        <div className="ml-[72px] mb-1 mr-3 overflow-auto rounded border border-[#2E3348] bg-[#242838] p-2">
          <pre className="font-mono text-[11px] leading-relaxed text-[#9CA3AF]">
            {JSON.stringify(entry.metadata, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
});

// --- Componente: Grupo de logs por fase ---

interface PhaseGroupProps {
  phase: LogPhase;
  entries: StructuredLogEntry[];
  defaultExpanded?: boolean;
}

const PhaseGroup = memo(function PhaseGroup({
  phase,
  entries,
  defaultExpanded = true,
}: PhaseGroupProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);

  const handleToggle = useCallback(() => {
    setExpanded((prev) => !prev);
  }, []);

  // Conta erros e warnings no grupo
  const errorCount = useMemo(
    () => entries.filter((e) => e.level === 'ERROR' || e.level === 'FATAL').length,
    [entries]
  );
  const warningCount = useMemo(
    () => entries.filter((e) => e.level === 'WARNING').length,
    [entries]
  );

  return (
    <div className="overflow-hidden rounded-lg border border-[#2E3348]">
      {/* Cabecalho do grupo */}
      <button
        type="button"
        onClick={handleToggle}
        className="flex w-full items-center gap-2 bg-[#242838] px-3 py-2 text-left transition-colors hover:bg-[#2A2F42]"
        aria-expanded={expanded}
        aria-label={`${expanded ? 'Recolher' : 'Expandir'} logs de ${PHASE_LABELS[phase] ?? phase}`}
      >
        {expanded ? (
          <ChevronDown className="size-3.5 text-[#9CA3AF]" />
        ) : (
          <ChevronRight className="size-3.5 text-[#9CA3AF]" />
        )}
        <span
          className={`inline-flex rounded px-1.5 py-0.5 text-xs font-medium ${PHASE_COLORS[phase] ?? 'bg-[#6B7280]/10 text-[#9CA3AF]'}`}
        >
          {PHASE_LABELS[phase] ?? phase}
        </span>
        <span className="text-xs text-[#6B7280]">
          ({entries.length} {entries.length === 1 ? 'entrada' : 'entradas'})
        </span>

        {/* Contadores de erro/warning */}
        <div className="ml-auto flex items-center gap-1.5">
          {errorCount > 0 && (
            <span className="inline-flex items-center gap-1 rounded bg-[#EF4444]/10 px-1.5 py-0.5 text-[10px] font-medium text-[#EF4444]">
              <XCircle className="size-3" />
              {errorCount}
            </span>
          )}
          {warningCount > 0 && (
            <span className="inline-flex items-center gap-1 rounded bg-[#F59E0B]/10 px-1.5 py-0.5 text-[10px] font-medium text-[#F59E0B]">
              <AlertTriangle className="size-3" />
              {warningCount}
            </span>
          )}
        </div>
      </button>

      {/* Entradas de log */}
      {expanded && (
        <div className="divide-y divide-[#2E3348]/50 bg-[#1A1D2E]">
          {entries.map((entry, index) => (
            <LogEntryRow
              key={`${entry.timestamp}-${index}`}
              entry={entry}
            />
          ))}
        </div>
      )}
    </div>
  );
});

// --- Props do componente principal ---

interface StructuredLogsProps {
  /** Logs estruturados (array de entradas) */
  structuredLogs: StructuredLogEntry[] | null;
  /** Logs em texto puro (fallback legado) */
  rawLogs: string | null;
}

/**
 * Componente de exibicao de logs estruturados.
 * Agrupa entradas por fase, com codificacao de cores por nivel
 * e metadados colapsaveis. Se structured_logs nao estiver disponivel,
 * exibe os logs em texto puro como fallback.
 */
const StructuredLogs = memo(function StructuredLogs({
  structuredLogs,
  rawLogs,
}: StructuredLogsProps) {
  const [logsExpanded, setLogsExpanded] = useState(false);

  const handleToggleLogs = useCallback(() => {
    setLogsExpanded((prev) => !prev);
  }, []);

  // Agrupa logs por fase mantendo a ordem de aparicao
  const groupedByPhase = useMemo(() => {
    if (!structuredLogs || structuredLogs.length === 0) return null;

    const groups: { phase: LogPhase; entries: StructuredLogEntry[] }[] = [];
    const phaseMap = new Map<string, number>();

    for (const entry of structuredLogs) {
      const existing = phaseMap.get(entry.phase);
      if (existing !== undefined) {
        groups[existing].entries.push(entry);
      } else {
        phaseMap.set(entry.phase, groups.length);
        groups.push({ phase: entry.phase, entries: [entry] });
      }
    }

    return groups;
  }, [structuredLogs]);

  const hasStructuredLogs = groupedByPhase !== null && groupedByPhase.length > 0;
  const hasRawLogs = rawLogs !== null && rawLogs.length > 0;
  const hasAnyLogs = hasStructuredLogs || hasRawLogs;

  return (
    <div className="rounded-xl border border-[#2E3348] bg-[#1A1D2E] p-6">
      {/* Cabecalho da secao */}
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <ScrollText className="size-5 text-[#F59E0B]" />
          <h2 className="text-base font-semibold text-[#F9FAFB]">
            Logs de Execucao
          </h2>
          {hasStructuredLogs && (
            <span className="text-xs text-[#6B7280]">
              ({structuredLogs!.length} {structuredLogs!.length === 1 ? 'entrada' : 'entradas'})
            </span>
          )}
        </div>

        {/* Botao expandir/recolher (apenas para logs raw no modo fallback) */}
        {!hasStructuredLogs && hasRawLogs && (
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

      {/* Conteudo dos logs */}
      {!hasAnyLogs ? (
        // Estado vazio
        <div className="py-4 text-center">
          <ScrollText className="mx-auto mb-2 size-8 text-[#6B7280]" />
          <p className="text-sm text-[#9CA3AF]">
            Nenhum log disponivel
          </p>
          <p className="mt-1 text-xs text-[#6B7280]">
            Os logs serao gerados durante a execucao.
          </p>
        </div>
      ) : hasStructuredLogs ? (
        // Logs estruturados agrupados por fase
        <div className="space-y-3">
          {groupedByPhase!.map((group) => (
            <PhaseGroup
              key={group.phase}
              phase={group.phase}
              entries={group.entries}
            />
          ))}
        </div>
      ) : (
        // Fallback: logs em texto puro (formato legado)
        <>
          <div
            className={`overflow-hidden transition-all duration-300 ${
              logsExpanded ? 'max-h-[none]' : 'max-h-64'
            }`}
          >
            <pre className="overflow-auto rounded-lg border border-[#2E3348] bg-[#242838] p-4 font-mono text-xs leading-relaxed text-[#F9FAFB] whitespace-pre-wrap">
              {rawLogs}
            </pre>
          </div>
          {/* Indicador de conteudo truncado */}
          {!logsExpanded && (
            <div className="relative -mt-8 h-8 bg-gradient-to-t from-[#1A1D2E] to-transparent" />
          )}
        </>
      )}
    </div>
  );
});

export { StructuredLogs };
export type { StructuredLogsProps };
