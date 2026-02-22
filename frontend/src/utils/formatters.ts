import { format, parseISO, formatDistanceToNow, isValid } from 'date-fns';
import { ptBR } from 'date-fns/locale';
import type { ExecutionStatus, DeliveryStatus } from '@/types';
import { EXECUTION_STATUS_MAP, DELIVERY_STATUS_MAP } from '@/utils/constants';

/**
 * Converte uma string de data para objeto Date de forma segura.
 * Retorna null se a data for inválida.
 */
function safeParseDate(date: string | Date | null | undefined): Date | null {
  if (!date) return null;

  const parsed = typeof date === 'string' ? parseISO(date) : date;
  return isValid(parsed) ? parsed : null;
}

/**
 * Formata uma data no formato brasileiro (dd/MM/yyyy).
 * Ex: "22/02/2026"
 */
export function formatDate(date: string | Date | null | undefined): string {
  const parsed = safeParseDate(date);
  if (!parsed) return '-';

  return format(parsed, 'dd/MM/yyyy', { locale: ptBR });
}

/**
 * Formata data e hora no formato brasileiro (dd/MM/yyyy HH:mm).
 * Ex: "22/02/2026 14:30"
 */
export function formatDateTime(date: string | Date | null | undefined): string {
  const parsed = safeParseDate(date);
  if (!parsed) return '-';

  return format(parsed, 'dd/MM/yyyy HH:mm', { locale: ptBR });
}

/**
 * Formata data e hora com segundos (dd/MM/yyyy HH:mm:ss).
 * Ex: "22/02/2026 14:30:45"
 */
export function formatDateTimeFull(date: string | Date | null | undefined): string {
  const parsed = safeParseDate(date);
  if (!parsed) return '-';

  return format(parsed, 'dd/MM/yyyy HH:mm:ss', { locale: ptBR });
}

/**
 * Formata uma data relativa em português.
 * Ex: "há 5 minutos", "há 2 horas"
 */
export function formatRelativeDate(date: string | Date | null | undefined): string {
  const parsed = safeParseDate(date);
  if (!parsed) return '-';

  return formatDistanceToNow(parsed, { addSuffix: true, locale: ptBR });
}

/**
 * Formata uma duração em segundos para formato legível em português.
 * Ex: 65 → "1min 5s", 3665 → "1h 1min 5s", 5 → "5s"
 */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || seconds < 0) return '-';

  if (seconds === 0) return '0s';

  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);

  const parts: string[] = [];

  if (hours > 0) parts.push(`${hours}h`);
  if (minutes > 0) parts.push(`${minutes}min`);
  if (secs > 0 || parts.length === 0) parts.push(`${secs}s`);

  return parts.join(' ');
}

/**
 * Retorna o label em português para um status de execução.
 * Ex: "success" → "Sucesso"
 */
export function formatExecutionStatus(status: ExecutionStatus): string {
  return EXECUTION_STATUS_MAP[status]?.label ?? status;
}

/**
 * Retorna o label em português para um status de entrega.
 * Ex: "sent" → "Enviado"
 */
export function formatDeliveryStatus(status: DeliveryStatus): string {
  return DELIVERY_STATUS_MAP[status]?.label ?? status;
}

/**
 * Trunca um texto para o comprimento máximo especificado.
 * Adiciona reticências se o texto for truncado.
 */
export function truncateText(
  text: string | null | undefined,
  maxLength: number = 50
): string {
  if (!text) return '';

  if (text.length <= maxLength) return text;

  return `${text.substring(0, maxLength)}...`;
}

/**
 * Formata uma expressão cron em texto legível (simplificado).
 * Retorna a expressão original se não conseguir interpretar.
 */
export function formatCronExpression(cron: string): string {
  if (!cron) return '-';

  const parts = cron.trim().split(/\s+/);
  if (parts.length !== 5) return cron;

  const [minute, hour, dayOfMonth, month, dayOfWeek] = parts;

  // Casos comuns simplificados
  if (minute === '0' && hour === '0' && dayOfMonth === '*' && month === '*' && dayOfWeek === '*') {
    return 'Diariamente à meia-noite';
  }

  if (dayOfMonth === '*' && month === '*' && dayOfWeek === '*') {
    if (minute !== '*' && hour !== '*') {
      return `Diariamente às ${hour.padStart(2, '0')}:${minute.padStart(2, '0')}`;
    }
  }

  if (minute.startsWith('*/') && hour === '*' && dayOfMonth === '*' && month === '*' && dayOfWeek === '*') {
    return `A cada ${minute.substring(2)} minutos`;
  }

  if (hour.startsWith('*/') && dayOfMonth === '*' && month === '*' && dayOfWeek === '*') {
    return `A cada ${hour.substring(2)} horas`;
  }

  // Retorna a expressão original se não for um caso comum
  return cron;
}
