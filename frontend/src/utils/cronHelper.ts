import { CronExpressionParser } from 'cron-parser';

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
