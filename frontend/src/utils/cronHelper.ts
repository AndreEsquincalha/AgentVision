import { CronExpressionParser } from 'cron-parser';

// --- Tipos ---

export type CronPreset =
  | 'every_15min'
  | 'every_30min'
  | 'every_1h'
  | 'every_n_hours'
  | 'daily'
  | 'weekdays'
  | 'weekly'
  | 'monthly'
  | 'custom';

export interface CronScheduleState {
  preset: CronPreset;
  hour: string;
  minute: string;
  dayOfWeek: string;
  dayOfMonth: string;
  intervalHours: string;
}

// --- Constantes ---

export interface CronPresetOption {
  value: CronPreset;
  label: string;
  group: string;
}

export const CRON_PRESETS: CronPresetOption[] = [
  { value: 'every_15min', label: 'A cada 15 minutos', group: 'Frequente' },
  { value: 'every_30min', label: 'A cada 30 minutos', group: 'Frequente' },
  { value: 'every_1h', label: 'A cada 1 hora', group: 'Frequente' },
  { value: 'every_n_hours', label: 'A cada N horas', group: 'Frequente' },
  { value: 'daily', label: 'Diariamente', group: 'Diario' },
  { value: 'weekdays', label: 'Dias uteis (seg-sex)', group: 'Diario' },
  { value: 'weekly', label: 'Semanalmente', group: 'Semanal / Mensal' },
  { value: 'monthly', label: 'Mensalmente', group: 'Semanal / Mensal' },
  { value: 'custom', label: 'Personalizado (cron)', group: 'Avancado' },
];

export const DAYS_OF_WEEK = [
  { value: '0', label: 'Domingo' },
  { value: '1', label: 'Segunda-feira' },
  { value: '2', label: 'Terca-feira' },
  { value: '3', label: 'Quarta-feira' },
  { value: '4', label: 'Quinta-feira' },
  { value: '5', label: 'Sexta-feira' },
  { value: '6', label: 'Sabado' },
];

export const HOUR_INTERVALS = [
  { value: '2', label: 'A cada 2 horas' },
  { value: '3', label: 'A cada 3 horas' },
  { value: '4', label: 'A cada 4 horas' },
  { value: '6', label: 'A cada 6 horas' },
  { value: '8', label: 'A cada 8 horas' },
  { value: '12', label: 'A cada 12 horas' },
];

// --- Geradores de opcoes ---

export function generateHourOptions(): { value: string; label: string }[] {
  return Array.from({ length: 24 }, (_, i) => ({
    value: String(i),
    label: String(i).padStart(2, '0'),
  }));
}

export function generateMinuteOptions(): { value: string; label: string }[] {
  return Array.from({ length: 12 }, (_, i) => {
    const val = i * 5;
    return {
      value: String(val),
      label: String(val).padStart(2, '0'),
    };
  });
}

// --- Build / Parse ---

/** Converte o estado da UI para uma expressao cron de 5 partes */
export function buildCronExpression(state: CronScheduleState): string {
  const { preset, hour, minute, dayOfWeek, dayOfMonth, intervalHours } = state;

  switch (preset) {
    case 'every_15min':
      return '*/15 * * * *';
    case 'every_30min':
      return '*/30 * * * *';
    case 'every_1h':
      return '0 * * * *';
    case 'every_n_hours':
      return `0 */${intervalHours || '2'} * * *`;
    case 'daily':
      return `${minute} ${hour} * * *`;
    case 'weekdays':
      return `${minute} ${hour} * * 1-5`;
    case 'weekly':
      return `${minute} ${hour} * * ${dayOfWeek}`;
    case 'monthly':
      return `${minute} ${hour} ${dayOfMonth} * *`;
    case 'custom':
      return '';
    default:
      return '';
  }
}

/** Tenta fazer o parse reverso de uma expressao cron para o estado da UI */
export function parseCronToState(cron: string): CronScheduleState {
  const defaultState: CronScheduleState = {
    preset: 'custom',
    hour: '8',
    minute: '0',
    dayOfWeek: '1',
    dayOfMonth: '1',
    intervalHours: '2',
  };

  if (!cron || !cron.trim()) return { ...defaultState, preset: 'daily' };

  const parts = cron.trim().split(/\s+/);
  if (parts.length !== 5) return defaultState;

  const [min, hr, dom, mon, dow] = parts;

  // */15 * * * *
  if (min === '*/15' && hr === '*' && dom === '*' && mon === '*' && dow === '*') {
    return { ...defaultState, preset: 'every_15min' };
  }

  // */30 * * * *
  if (min === '*/30' && hr === '*' && dom === '*' && mon === '*' && dow === '*') {
    return { ...defaultState, preset: 'every_30min' };
  }

  // 0 * * * *
  if (min === '0' && hr === '*' && dom === '*' && mon === '*' && dow === '*') {
    return { ...defaultState, preset: 'every_1h' };
  }

  // 0 */N * * *
  if (min === '0' && hr.startsWith('*/') && dom === '*' && mon === '*' && dow === '*') {
    const interval = hr.substring(2);
    if (['2', '3', '4', '6', '8', '12'].includes(interval)) {
      return { ...defaultState, preset: 'every_n_hours', intervalHours: interval };
    }
  }

  // M H * * 1-5 (dias uteis)
  if (dom === '*' && mon === '*' && dow === '1-5' && !min.includes('*') && !hr.includes('*')) {
    return { ...defaultState, preset: 'weekdays', minute: min, hour: hr };
  }

  // M H * * D (semanal - dia especifico)
  if (dom === '*' && mon === '*' && dow !== '*' && !dow.includes('-') && !dow.includes(',')
    && !min.includes('*') && !hr.includes('*')) {
    return { ...defaultState, preset: 'weekly', minute: min, hour: hr, dayOfWeek: dow };
  }

  // M H D * * (mensal)
  if (mon === '*' && dow === '*' && dom !== '*' && !dom.includes('*')
    && !min.includes('*') && !hr.includes('*')) {
    return { ...defaultState, preset: 'monthly', minute: min, hour: hr, dayOfMonth: dom };
  }

  // M H * * * (diario)
  if (dom === '*' && mon === '*' && dow === '*' && !min.includes('*') && !hr.includes('*')) {
    return { ...defaultState, preset: 'daily', minute: min, hour: hr };
  }

  // Nao reconhecido => custom
  return defaultState;
}

/**
 * Calcula as proximas N datas de execucao a partir de uma expressao cron.
 * Retorna um array de strings ISO para uso com formatDateTime.
 * Retorna array vazio se a expressao for invalida.
 */
export function getNextCronExecutions(
  cronExpression: string,
  count: number = 5
): string[] {
  if (!cronExpression || !cronExpression.trim()) return [];

  try {
    const interval = CronExpressionParser.parse(cronExpression.trim(), {
      currentDate: new Date(),
    });

    const dates: string[] = [];
    for (let i = 0; i < count; i++) {
      const next = interval.next();
      const iso = next.toISOString();
      if (iso) {
        dates.push(iso);
      }
    }

    return dates;
  } catch {
    return [];
  }
}

/**
 * Valida se uma expressao cron e sintaticamente valida.
 */
export function isValidCronExpression(cronExpression: string): boolean {
  if (!cronExpression || !cronExpression.trim()) return false;

  try {
    CronExpressionParser.parse(cronExpression.trim());
    return true;
  } catch {
    return false;
  }
}
