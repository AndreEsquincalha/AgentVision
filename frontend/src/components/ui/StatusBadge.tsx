import { memo } from 'react';
import {
  CheckCircle2,
  XCircle,
  Loader2,
  Clock,
  AlertTriangle,
  Send,
} from 'lucide-react';
import type { ExecutionStatus, DeliveryStatus } from '@/types';
import {
  EXECUTION_STATUS_MAP,
  DELIVERY_STATUS_MAP,
} from '@/utils/constants';
import type { StatusConfig } from '@/utils/constants';
import { cn } from '@/lib/utils';

// --- Tipos ---

type StatusType = ExecutionStatus | DeliveryStatus | 'warning';

interface StatusBadgeProps {
  /** Status a ser exibido */
  status: StatusType;
  /** Tipo de mapeamento de status a usar */
  variant?: 'execution' | 'delivery';
  /** Classes CSS adicionais */
  className?: string;
}

// --- Mapeamento de ícones por status ---

const STATUS_ICONS: Record<string, React.ComponentType<React.SVGProps<SVGSVGElement> & { className?: string }>> = {
  success: CheckCircle2,
  failed: XCircle,
  error: XCircle,
  running: Loader2,
  pending: Clock,
  warning: AlertTriangle,
  sent: Send,
};

// --- Config de warning (não existe nos mapas padrão) ---

const WARNING_CONFIG: StatusConfig = {
  label: 'Alerta',
  color: '#F59E0B',
  bgClass: 'bg-[#F59E0B]/10',
  textClass: 'text-[#F59E0B]',
};

/**
 * Retorna a configuração de status com base no tipo e variante.
 */
function getStatusConfig(
  status: StatusType,
  variant: 'execution' | 'delivery'
): StatusConfig {
  if (status === 'warning') return WARNING_CONFIG;

  if (variant === 'delivery') {
    return DELIVERY_STATUS_MAP[status as DeliveryStatus] ?? EXECUTION_STATUS_MAP[status as ExecutionStatus];
  }

  return EXECUTION_STATUS_MAP[status as ExecutionStatus] ?? DELIVERY_STATUS_MAP[status as DeliveryStatus];
}

/**
 * Badge de status reutilizável com cor e ícone automáticos.
 * Suporta status de execução, entrega e alerta genérico.
 * O status "running" exibe um ícone animado com rotação.
 */
const StatusBadge = memo(function StatusBadge({
  status,
  variant = 'execution',
  className,
}: StatusBadgeProps) {
  const config = getStatusConfig(status, variant);
  const Icon = STATUS_ICONS[status];

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium',
        config.bgClass,
        config.textClass,
        className
      )}
      aria-label={`Status: ${config.label}`}
    >
      {Icon && (
        <Icon
          className={cn(
            'size-3',
            status === 'running' && 'animate-spin'
          )}
        />
      )}
      {config.label}
    </span>
  );
});

export { StatusBadge };
export type { StatusBadgeProps, StatusType };
