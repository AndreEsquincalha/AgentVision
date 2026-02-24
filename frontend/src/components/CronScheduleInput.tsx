import { useState, useCallback, useMemo, useRef, useEffect } from 'react';
import { Controller, type Control } from 'react-hook-form';
import { CalendarClock, Code } from 'lucide-react';
import { Label } from '@/components/ui/label';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectLabel,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  CRON_PRESETS,
  DAYS_OF_WEEK,
  HOUR_INTERVALS,
  generateHourOptions,
  generateMinuteOptions,
  buildCronExpression,
  parseCronToState,
  getNextCronExecutions,
  type CronScheduleState,
  type CronPreset,
} from '@/utils/cronHelper';
import { formatCronExpression } from '@/utils/formatters';
import { formatDateTime } from '@/utils/formatters';

// --- Estilos reutilizaveis ---
const selectTriggerClass =
  'w-full border-[#2E3348] bg-[#242838] text-[#F9FAFB] focus:border-[#6366F1] focus:ring-[#6366F1]';
const selectContentClass = 'border-[#2E3348] bg-[#242838]';
const selectItemClass =
  'text-[#F9FAFB] focus:bg-[#2A2F42] focus:text-[#F9FAFB]';

// Opcoes pre-geradas (constantes)
const HOUR_OPTIONS = generateHourOptions();
const MINUTE_OPTIONS = generateMinuteOptions();

// Agrupa presets por grupo
const PRESET_GROUPS = CRON_PRESETS.reduce<
  Record<string, typeof CRON_PRESETS>
>((acc, preset) => {
  if (!acc[preset.group]) acc[preset.group] = [];
  acc[preset.group].push(preset);
  return acc;
}, {});

// --- Props ---

interface CronScheduleInputProps {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  control: Control<any>;
  error?: string;
}

/**
 * Componente de input de agendamento cron com presets visuais.
 * Controlado via react-hook-form Controller.
 */
function CronScheduleInput({ control, error }: CronScheduleInputProps) {
  return (
    <Controller
      name="cron_expression"
      control={control}
      render={({ field }) => (
        <CronScheduleInputInner
          value={field.value}
          onChange={field.onChange}
          error={error}
        />
      )}
    />
  );
}

// --- Componente interno ---

interface CronScheduleInputInnerProps {
  value: string;
  onChange: (value: string) => void;
  error?: string;
}

function CronScheduleInputInner({
  value,
  onChange,
  error,
}: CronScheduleInputInnerProps) {
  // Ref para evitar loops de sincronizacao bidirecional
  const isInternalChange = useRef(false);

  // Estado interno da UI
  const [state, setState] = useState<CronScheduleState>(() =>
    parseCronToState(value)
  );

  // Expressao cron manual (para modo custom)
  const [customCron, setCustomCron] = useState(() =>
    parseCronToState(value).preset === 'custom' ? value : ''
  );

  // Sincroniza valor externo -> estado interno (ex: reset do form)
  useEffect(() => {
    if (isInternalChange.current) {
      isInternalChange.current = false;
      return;
    }
    const parsed = parseCronToState(value);
    setState(parsed);
    if (parsed.preset === 'custom') {
      setCustomCron(value);
    }
  }, [value]);

  // Atualiza o field do form quando o estado muda
  const syncToForm = useCallback(
    (newState: CronScheduleState, customValue?: string) => {
      isInternalChange.current = true;
      if (newState.preset === 'custom') {
        onChange(customValue ?? customCron);
      } else {
        const cron = buildCronExpression(newState);
        onChange(cron);
      }
    },
    [onChange, customCron]
  );

  // Handler para mudanca de preset
  const handlePresetChange = useCallback(
    (preset: string) => {
      const newState: CronScheduleState = {
        ...state,
        preset: preset as CronPreset,
      };
      setState(newState);
      syncToForm(newState);
    },
    [state, syncToForm]
  );

  // Handler generico para mudanca de campo
  const handleFieldChange = useCallback(
    (field: keyof CronScheduleState, val: string) => {
      const newState = { ...state, [field]: val };
      setState(newState);
      syncToForm(newState);
    },
    [state, syncToForm]
  );

  // Handler para cron manual
  const handleCustomCronChange = useCallback(
    (val: string) => {
      setCustomCron(val);
      isInternalChange.current = true;
      onChange(val);
    },
    [onChange]
  );

  // Preview das proximas execucoes
  const cronExpression =
    state.preset === 'custom' ? customCron : buildCronExpression(state);

  const nextExecutions = useMemo(
    () => getNextCronExecutions(cronExpression, 5),
    [cronExpression]
  );

  // Texto legivel da expressao cron
  const cronReadable = useMemo(
    () => (cronExpression ? formatCronExpression(cronExpression) : ''),
    [cronExpression]
  );

  // Determina se mostra campos de hora/minuto
  const showTimeFields = ['daily', 'weekdays', 'weekly', 'monthly'].includes(
    state.preset
  );

  return (
    <div className="space-y-4">
      {/* Select de preset */}
      <div>
        <Label className="mb-1.5 text-sm font-medium text-[#F9FAFB]">
          Frequencia *
        </Label>
        <Select value={state.preset} onValueChange={handlePresetChange}>
          <SelectTrigger
            className={selectTriggerClass}
            aria-invalid={error ? 'true' : 'false'}
          >
            <SelectValue placeholder="Selecione a frequencia" />
          </SelectTrigger>
          <SelectContent className={selectContentClass}>
            {Object.entries(PRESET_GROUPS).map(([group, presets]) => (
              <SelectGroup key={group}>
                <SelectLabel className="text-xs font-semibold uppercase tracking-wider text-[#6B7280]">
                  {group}
                </SelectLabel>
                {presets.map((preset) => (
                  <SelectItem
                    key={preset.value}
                    value={preset.value}
                    className={selectItemClass}
                  >
                    {preset.label}
                  </SelectItem>
                ))}
              </SelectGroup>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Campos contextuais */}
      <div className="flex flex-wrap gap-3">
        {/* Intervalo de horas (every_n_hours) */}
        {state.preset === 'every_n_hours' && (
          <div className="min-w-[180px] flex-1">
            <Label className="mb-1.5 text-xs font-medium text-[#9CA3AF]">
              Intervalo
            </Label>
            <Select
              value={state.intervalHours}
              onValueChange={(v) => handleFieldChange('intervalHours', v)}
            >
              <SelectTrigger className={selectTriggerClass}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent className={selectContentClass}>
                {HOUR_INTERVALS.map((opt) => (
                  <SelectItem
                    key={opt.value}
                    value={opt.value}
                    className={selectItemClass}
                  >
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        {/* Hora e minuto */}
        {showTimeFields && (
          <>
            <div className="min-w-[100px]">
              <Label className="mb-1.5 text-xs font-medium text-[#9CA3AF]">
                Hora
              </Label>
              <Select
                value={state.hour}
                onValueChange={(v) => handleFieldChange('hour', v)}
              >
                <SelectTrigger className={selectTriggerClass}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className={selectContentClass}>
                  {HOUR_OPTIONS.map((opt) => (
                    <SelectItem
                      key={opt.value}
                      value={opt.value}
                      className={selectItemClass}
                    >
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="min-w-[100px]">
              <Label className="mb-1.5 text-xs font-medium text-[#9CA3AF]">
                Minuto
              </Label>
              <Select
                value={state.minute}
                onValueChange={(v) => handleFieldChange('minute', v)}
              >
                <SelectTrigger className={selectTriggerClass}>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent className={selectContentClass}>
                  {MINUTE_OPTIONS.map((opt) => (
                    <SelectItem
                      key={opt.value}
                      value={opt.value}
                      className={selectItemClass}
                    >
                      {opt.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </>
        )}

        {/* Dia da semana (weekly) */}
        {state.preset === 'weekly' && (
          <div className="min-w-[180px] flex-1">
            <Label className="mb-1.5 text-xs font-medium text-[#9CA3AF]">
              Dia da semana
            </Label>
            <Select
              value={state.dayOfWeek}
              onValueChange={(v) => handleFieldChange('dayOfWeek', v)}
            >
              <SelectTrigger className={selectTriggerClass}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent className={selectContentClass}>
                {DAYS_OF_WEEK.map((opt) => (
                  <SelectItem
                    key={opt.value}
                    value={opt.value}
                    className={selectItemClass}
                  >
                    {opt.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        {/* Dia do mes (monthly) */}
        {state.preset === 'monthly' && (
          <div className="min-w-[120px]">
            <Label className="mb-1.5 text-xs font-medium text-[#9CA3AF]">
              Dia do mes
            </Label>
            <Select
              value={state.dayOfMonth}
              onValueChange={(v) => handleFieldChange('dayOfMonth', v)}
            >
              <SelectTrigger className={selectTriggerClass}>
                <SelectValue />
              </SelectTrigger>
              <SelectContent className={selectContentClass}>
                {Array.from({ length: 28 }, (_, i) => (
                  <SelectItem
                    key={i + 1}
                    value={String(i + 1)}
                    className={selectItemClass}
                  >
                    {String(i + 1)}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        )}

        {/* Input cron manual (custom) */}
        {state.preset === 'custom' && (
          <div className="w-full">
            <Label className="mb-1.5 text-xs font-medium text-[#9CA3AF]">
              Expressao Cron
            </Label>
            <Input
              value={customCron}
              onChange={(e) => handleCustomCronChange(e.target.value)}
              placeholder="0 8 * * * (minuto hora dia mes dia_semana)"
              className="border-[#2E3348] bg-[#242838] font-mono text-[#F9FAFB] placeholder-[#6B7280] focus:border-[#6366F1] focus:ring-[#6366F1]"
            />
            <p className="mt-1 text-xs text-[#6B7280]">
              Formato: minuto hora dia_mes mes dia_semana (ex: 0 8 * * 1-5 =
              dias uteis as 08:00)
            </p>
          </div>
        )}
      </div>

      {/* Erro de validacao */}
      {error && (
        <p className="text-xs text-[#EF4444]" role="alert">
          {error}
        </p>
      )}

      {/* Badge com expressao cron + texto legivel */}
      {cronExpression && (
        <div className="flex flex-wrap items-center gap-2">
          <Badge className="border-[#2E3348] bg-[#242838] font-mono text-xs text-[#9CA3AF]">
            <Code className="size-3" />
            {cronExpression}
          </Badge>
          {cronReadable !== cronExpression && (
            <span className="text-xs text-[#6B7280]">{cronReadable}</span>
          )}
        </div>
      )}

      {/* Preview das proximas execucoes */}
      {nextExecutions.length > 0 && (
        <div className="rounded-lg border border-[#2E3348] bg-[#242838] p-3">
          <div className="mb-2 flex items-center gap-1.5">
            <CalendarClock className="size-3.5 text-[#6366F1]" />
            <span className="text-xs font-medium text-[#9CA3AF]">
              Proximas execucoes
            </span>
          </div>
          <ul className="space-y-1">
            {nextExecutions.map((date, index) => (
              <li key={index} className="text-xs text-[#F9FAFB]">
                {formatDateTime(date)}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

export { CronScheduleInput };
export type { CronScheduleInputProps };
