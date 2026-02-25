import { memo, useMemo } from 'react';
import { Loader2 } from 'lucide-react';
import type { ExecutionStatus } from '@/types';

// --- Configuracao de fases do progresso ---

interface ProgressPhase {
  /** Limite minimo da faixa (inclusive) */
  min: number;
  /** Limite maximo da faixa (exclusive, exceto ultima) */
  max: number;
  /** Rotulo exibido ao usuario */
  label: string;
  /** Cor da barra de progresso */
  barColor: string;
  /** Cor do texto do rotulo */
  textColor: string;
}

const PROGRESS_PHASES: ProgressPhase[] = [
  {
    min: 0,
    max: 20,
    label: 'Iniciando...',
    barColor: 'bg-[#6B7280]',
    textColor: 'text-[#9CA3AF]',
  },
  {
    min: 20,
    max: 40,
    label: 'Navegando...',
    barColor: 'bg-[#6366F1]',
    textColor: 'text-[#818CF8]',
  },
  {
    min: 40,
    max: 60,
    label: 'Capturando screenshots...',
    barColor: 'bg-[#6366F1]',
    textColor: 'text-[#818CF8]',
  },
  {
    min: 60,
    max: 75,
    label: 'Analisando com IA...',
    barColor: 'bg-[#8B5CF6]',
    textColor: 'text-[#A78BFA]',
  },
  {
    min: 75,
    max: 90,
    label: 'Gerando PDF...',
    barColor: 'bg-[#8B5CF6]',
    textColor: 'text-[#A78BFA]',
  },
  {
    min: 90,
    max: 101,
    label: 'Finalizando...',
    barColor: 'bg-[#10B981]',
    textColor: 'text-[#10B981]',
  },
];

/**
 * Retorna a fase correspondente ao percentual de progresso.
 */
function getPhaseForPercent(percent: number): ProgressPhase {
  const clamped = Math.max(0, Math.min(100, percent));
  for (const phase of PROGRESS_PHASES) {
    if (clamped >= phase.min && clamped < phase.max) {
      return phase;
    }
  }
  // Fallback para a ultima fase
  return PROGRESS_PHASES[PROGRESS_PHASES.length - 1];
}

// --- Props ---

interface ExecutionProgressBarProps {
  /** Percentual de progresso (0-100) */
  progressPercent: number;
  /** Status da execucao */
  status: ExecutionStatus;
}

/**
 * Barra de progresso visual para execucoes em andamento.
 * Exibe o percentual, rotulo da fase atual e uma barra animada.
 * So e renderizado quando o status e 'running' ou 'pending'.
 */
const ExecutionProgressBar = memo(function ExecutionProgressBar({
  progressPercent,
  status,
}: ExecutionProgressBarProps) {
  const phase = useMemo(
    () => getPhaseForPercent(progressPercent),
    [progressPercent]
  );

  const clampedPercent = useMemo(
    () => Math.max(0, Math.min(100, progressPercent)),
    [progressPercent]
  );

  // So exibe para execucoes em andamento ou pendentes
  const isVisible = status === 'running' || status === 'pending';

  if (!isVisible) {
    return null;
  }

  return (
    <div
      className="rounded-xl border border-[#2E3348] bg-[#1A1D2E] p-6"
      role="progressbar"
      aria-valuenow={clampedPercent}
      aria-valuemin={0}
      aria-valuemax={100}
      aria-label={`Progresso da execução: ${clampedPercent}% - ${phase.label}`}
    >
      {/* Cabecalho com rotulo e percentual */}
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Loader2 className="size-4 animate-spin text-[#22D3EE]" />
          <span className={`text-sm font-medium ${phase.textColor}`}>
            {phase.label}
          </span>
        </div>
        <span className="text-sm font-semibold text-[#F9FAFB]">
          {clampedPercent}%
        </span>
      </div>

      {/* Barra de progresso */}
      <div className="h-2 w-full overflow-hidden rounded-full bg-[#242838]">
        <div
          className={`h-full rounded-full transition-all duration-500 ease-out ${phase.barColor}`}
          style={{ width: `${clampedPercent}%` }}
        />
      </div>

      {/* Indicadores de fase (mini-etapas) */}
      <div className="mt-3 flex items-center justify-between">
        {PROGRESS_PHASES.map((p) => {
          const isActive = clampedPercent >= p.min;
          const isCurrent = clampedPercent >= p.min && clampedPercent < p.max;
          return (
            <div
              key={p.label}
              className="flex flex-col items-center"
            >
              <div
                className={`size-2 rounded-full transition-colors ${
                  isCurrent
                    ? 'animate-pulse bg-[#22D3EE]'
                    : isActive
                      ? 'bg-[#6366F1]'
                      : 'bg-[#2E3348]'
                }`}
              />
              <span
                className={`mt-1 hidden text-[10px] sm:block ${
                  isCurrent
                    ? 'font-medium text-[#F9FAFB]'
                    : isActive
                      ? 'text-[#9CA3AF]'
                      : 'text-[#6B7280]'
                }`}
              >
                {p.label.replace('...', '')}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
});

export { ExecutionProgressBar };
export type { ExecutionProgressBarProps };
