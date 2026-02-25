import { memo, useCallback, useEffect, useMemo } from 'react';
import { useForm, Controller, useFieldArray } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Loader2, Plus, Trash2 } from 'lucide-react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Textarea } from '@/components/ui/textarea';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Separator } from '@/components/ui/separator';
import { Switch } from '@/components/ui/switch';
import { CronScheduleInput } from '@/components/CronScheduleInput';
import { useCreateJob, useUpdateJob } from '@/hooks/useJobs';
import { useProjects } from '@/hooks/useProjects';
import { isValidCronExpression } from '@/utils/cronHelper';
import { cn } from '@/lib/utils';
import type { Job } from '@/types';

// --- Funções auxiliares de validação ---

/** Valida se uma string é JSON válido */
function isValidJson(str: string): boolean {
  if (!str.trim()) return true;
  try {
    const parsed = JSON.parse(str);
    return typeof parsed === 'object' && parsed !== null;
  } catch {
    return false;
  }
}

/** Valida lista de emails separados por vírgula */
function validateEmailList(str: string): string | true {
  const emails = str.split(',').map((e) => e.trim()).filter(Boolean);
  if (emails.length === 0) return 'Informe pelo menos um destinatário';
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  const invalidEmails = emails.filter((e) => !emailRegex.test(e));
  if (invalidEmails.length > 0) {
    return `E-mail(s) inválido(s): ${invalidEmails.join(', ')}`;
  }
  return true;
}

/** Valida lista de URLs/endpoints para webhook */
function validateWebhookList(str: string): string | true {
  const urls = str.split(',').map((u) => u.trim()).filter(Boolean);
  if (urls.length === 0) return 'Informe pelo menos uma URL';
  const urlRegex = /^https?:\/\/.+/i;
  const invalidUrls = urls.filter((u) => !urlRegex.test(u));
  if (invalidUrls.length > 0) {
    return `URL(s) inválida(s): ${invalidUrls.join(', ')}. Use http:// ou https://`;
  }
  return true;
}

// --- Schema de validação ---

const deliveryConfigSchema = z.object({
  channel_type: z.enum(['email', 'onedrive', 'webhook'], {
    error: 'Tipo de canal é obrigatório',
  }),
  recipients: z
    .string({ error: 'Destinatários são obrigatórios' })
    .min(1, 'Informe pelo menos um destinatário'),
  is_active: z.boolean().optional(),
});

const jobFormSchema = z.object({
  project_id: z
    .string({ error: 'Projeto é obrigatório' })
    .min(1, 'Selecione um projeto'),
  name: z
    .string({ error: 'Nome é obrigatório' })
    .min(3, 'Nome deve ter pelo menos 3 caracteres'),
  cron_expression: z
    .string({ error: 'Expressão cron é obrigatória' })
    .min(1, 'Expressão cron é obrigatória')
    .regex(
      /^(\S+\s+){4}\S+$/,
      'Expressão cron inválida. Use o formato: minuto hora dia mês dia_semana'
    )
    .refine(
      (val) => isValidCronExpression(val),
      'Expressão cron inválida. Verifique os valores informados.'
    ),
  agent_prompt: z
    .string({ error: 'Prompt é obrigatório' })
    .min(10, 'Prompt deve ter pelo menos 10 caracteres'),
  prompt_template_id: z.string().optional(),
  execution_params: z
    .string()
    .optional()
    .refine(
      (val) => !val || isValidJson(val),
      'JSON inválido. Verifique a sintaxe do JSON.'
    ),
  notify_on_failure: z.boolean(),
  delivery_configs: z.array(deliveryConfigSchema).optional(),
});

type JobFormData = z.infer<typeof jobFormSchema>;

// --- Props ---

interface JobFormProps {
  /** Se o dialog esta aberto */
  open: boolean;
  /** Callback para abrir/fechar */
  onOpenChange: (open: boolean) => void;
  /** Job existente para edicao (null = criacao) */
  job?: Job | null;
}

/**
 * Formulario de criacao/edicao de jobs em formato modal (Dialog).
 * Usa react-hook-form + zod para validacao e shadcn/ui para componentes.
 */
const JobForm = memo(function JobForm({
  open,
  onOpenChange,
  job,
}: JobFormProps) {
  const isEditing = !!job;
  const createMutation = useCreateJob();
  const updateMutation = useUpdateJob();
  const isSubmitting = createMutation.isPending || updateMutation.isPending;

  // Busca lista de projetos para o select
  const { data: projectsData } = useProjects({ per_page: 100 });
  const projects = useMemo(
    () => projectsData?.items ?? [],
    [projectsData]
  );

  // Valores padrao do formulario
  const defaultValues = useMemo<JobFormData>(
    () => ({
      project_id: job?.project_id ?? '',
      name: job?.name ?? '',
      cron_expression: job?.cron_expression ?? '',
      agent_prompt: job?.agent_prompt ?? '',
      prompt_template_id: job?.prompt_template_id ?? '',
      execution_params: job?.execution_params
        ? JSON.stringify(job.execution_params, null, 2)
        : '',
      notify_on_failure: job?.notify_on_failure ?? true,
      delivery_configs: job?.delivery_configs?.map((dc) => ({
        channel_type: dc.channel_type,
        recipients: dc.recipients.join(', '),
        is_active: dc.is_active,
      })) ?? [],
    }),
    [job]
  );

  const {
    register,
    handleSubmit,
    control,
    reset,
    setError,
    watch,
    formState: { errors },
  } = useForm<JobFormData>({
    resolver: zodResolver(jobFormSchema),
    defaultValues,
  });

  const { fields, append, remove } = useFieldArray({
    control,
    name: 'delivery_configs',
  });

  // Reseta o formulario quando o dialog abre/fecha ou o job muda
  useEffect(() => {
    if (open) {
      reset(defaultValues);
    }
  }, [open, defaultValues, reset]);

  // Adiciona um novo canal de entrega
  const handleAddDeliveryConfig = useCallback(() => {
    append({
      channel_type: 'email',
      recipients: '',
      is_active: true,
    });
  }, [append]);

  // Callback de submissao
  const onSubmit = useCallback(
    async (data: JobFormData) => {
      // Valida destinatários de entrega por tipo de canal
      if (data.delivery_configs && data.delivery_configs.length > 0) {
        for (let i = 0; i < data.delivery_configs.length; i++) {
          const dc = data.delivery_configs[i];
          if (dc.channel_type === 'email') {
            const result = validateEmailList(dc.recipients);
            if (result !== true) {
              setError(`delivery_configs.${i}.recipients`, {
                type: 'manual',
                message: result,
              });
              return;
            }
          } else if (dc.channel_type === 'webhook') {
            const result = validateWebhookList(dc.recipients);
            if (result !== true) {
              setError(`delivery_configs.${i}.recipients`, {
                type: 'manual',
                message: result,
              });
              return;
            }
          }
        }
      }

      // Monta o payload para a API
      let executionParams: Record<string, unknown> | undefined;
      if (data.execution_params) {
        executionParams = JSON.parse(data.execution_params);
      }

      const payload = {
        project_id: data.project_id,
        name: data.name,
        cron_expression: data.cron_expression,
        agent_prompt: data.agent_prompt,
        prompt_template_id: data.prompt_template_id || undefined,
        execution_params: executionParams,
        notify_on_failure: data.notify_on_failure,
        delivery_configs: data.delivery_configs?.map((dc) => ({
          channel_type: dc.channel_type as 'email' | 'onedrive' | 'webhook',
          recipients: dc.recipients
            .split(',')
            .map((r) => r.trim())
            .filter(Boolean),
          channel_config: {},
          is_active: dc.is_active ?? true,
        })),
      };

      try {
        if (isEditing && job) {
          await updateMutation.mutateAsync({ id: job.id, data: payload });
        } else {
          await createMutation.mutateAsync(payload);
        }
        onOpenChange(false);
      } catch {
        // Erro ja tratado no hook (toast)
      }
    },
    [isEditing, job, createMutation, updateMutation, onOpenChange, setError]
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto border-[#2E3348] bg-[#1A1D2E] sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="text-lg font-semibold text-[#F9FAFB]">
            {isEditing ? 'Editar Job' : 'Novo Job'}
          </DialogTitle>
          <DialogDescription className="text-sm text-[#9CA3AF]">
            {isEditing
              ? 'Atualize as configurações do job.'
              : 'Configure um novo job de automação.'}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
          {/* Secao: Dados basicos */}
          <div>
            <h3 className="mb-3 text-sm font-medium uppercase tracking-wider text-[#9CA3AF]">
              Dados Básicos
            </h3>
            <div className="space-y-4">
              {/* Projeto */}
              <div>
                <Label
                  htmlFor="project_id"
                  className="mb-1.5 text-sm font-medium text-[#F9FAFB]"
                >
                  Projeto *
                </Label>
                <Controller
                  name="project_id"
                  control={control}
                  render={({ field }) => (
                    <Select
                      value={field.value}
                      onValueChange={field.onChange}
                    >
                      <SelectTrigger
                        id="project_id"
                        className="w-full border-[#2E3348] bg-[#242838] text-[#F9FAFB] focus:border-[#6366F1] focus:ring-[#6366F1]"
                        aria-invalid={errors.project_id ? 'true' : 'false'}
                      >
                        <SelectValue placeholder="Selecione um projeto" />
                      </SelectTrigger>
                      <SelectContent className="border-[#2E3348] bg-[#242838]">
                        {projects.map((project) => (
                          <SelectItem
                            key={project.id}
                            value={project.id}
                            className="text-[#F9FAFB] focus:bg-[#2A2F42] focus:text-[#F9FAFB]"
                          >
                            {project.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  )}
                />
                {errors.project_id && (
                  <p className="mt-1 text-xs text-[#EF4444]" role="alert">
                    {errors.project_id.message}
                  </p>
                )}
              </div>

              {/* Nome */}
              <div>
                <Label
                  htmlFor="job_name"
                  className="mb-1.5 text-sm font-medium text-[#F9FAFB]"
                >
                  Nome *
                </Label>
                <Input
                  id="job_name"
                  placeholder="Ex: Captura diária de relatório"
                  aria-invalid={errors.name ? 'true' : 'false'}
                  aria-describedby={errors.name ? 'name-error' : undefined}
                  className={cn(
                    'border-[#2E3348] bg-[#242838] text-[#F9FAFB] placeholder-[#6B7280] focus:border-[#6366F1] focus:ring-[#6366F1]',
                    errors.name && 'border-[#EF4444] focus:border-[#EF4444] focus:ring-[#EF4444]'
                  )}
                  {...register('name')}
                />
                {errors.name && (
                  <p
                    id="name-error"
                    className="mt-1 text-xs text-[#EF4444]"
                    role="alert"
                  >
                    {errors.name.message}
                  </p>
                )}
              </div>
            </div>
          </div>

          <Separator className="bg-[#2E3348]" />

          {/* Secao: Agendamento */}
          <div>
            <h3 className="mb-3 text-sm font-medium uppercase tracking-wider text-[#9CA3AF]">
              Agendamento
            </h3>
            <CronScheduleInput
              control={control}
              error={errors.cron_expression?.message}
            />
          </div>

          <Separator className="bg-[#2E3348]" />

          {/* Secao: Prompt do agente */}
          <div>
            <h3 className="mb-3 text-sm font-medium uppercase tracking-wider text-[#9CA3AF]">
              Prompt do Agente
            </h3>
            <div className="space-y-4">
              {/* Prompt */}
              <div>
                <Label
                  htmlFor="agent_prompt"
                  className="mb-1.5 text-sm font-medium text-[#F9FAFB]"
                >
                  Prompt *
                </Label>
                <Textarea
                  id="agent_prompt"
                  placeholder="Descreva as instruções para o agente de IA. Ex: Navegue até a página de relatórios, capture screenshots e analise os dados..."
                  rows={5}
                  aria-invalid={errors.agent_prompt ? 'true' : 'false'}
                  aria-describedby={
                    errors.agent_prompt ? 'prompt-error' : undefined
                  }
                  className={cn(
                    'border-[#2E3348] bg-[#242838] text-[#F9FAFB] placeholder-[#6B7280] focus:border-[#6366F1] focus:ring-[#6366F1]',
                    errors.agent_prompt && 'border-[#EF4444] focus:border-[#EF4444] focus:ring-[#EF4444]'
                  )}
                  {...register('agent_prompt')}
                />
                {errors.agent_prompt && (
                  <p
                    id="prompt-error"
                    className="mt-1 text-xs text-[#EF4444]"
                    role="alert"
                  >
                    {errors.agent_prompt.message}
                  </p>
                )}
              </div>

              {/* Parametros de execucao (JSON) */}
              <div>
                <Label
                  htmlFor="execution_params"
                  className="mb-1.5 text-sm font-medium text-[#F9FAFB]"
                >
                  Parâmetros de Execução (JSON)
                </Label>
                <Textarea
                  id="execution_params"
                  placeholder='{"chave": "valor"}'
                  rows={3}
                  aria-invalid={errors.execution_params ? 'true' : 'false'}
                  aria-describedby={
                    errors.execution_params ? 'exec-params-error' : undefined
                  }
                  className={cn(
                    'border-[#2E3348] bg-[#242838] font-mono text-sm text-[#F9FAFB] placeholder-[#6B7280] focus:border-[#6366F1] focus:ring-[#6366F1]',
                    errors.execution_params && 'border-[#EF4444] focus:border-[#EF4444] focus:ring-[#EF4444]'
                  )}
                  {...register('execution_params')}
                />
                {errors.execution_params ? (
                  <p
                    id="exec-params-error"
                    className="mt-1 text-xs text-[#EF4444]"
                    role="alert"
                  >
                    {errors.execution_params.message}
                  </p>
                ) : (
                  <p className="mt-1 text-xs text-[#6B7280]">
                    Opcional. JSON com parâmetros extras para a execução.
                  </p>
                )}
              </div>
            </div>
          </div>

          <Separator className="bg-[#2E3348]" />

          {/* Secao: Notificacoes */}
          <div>
            <h3 className="mb-3 text-sm font-medium uppercase tracking-wider text-[#9CA3AF]">
              Notificacoes
            </h3>
            <div className="flex items-center justify-between rounded-lg border border-[#2E3348] bg-[#242838] px-4 py-3">
              <div>
                <Label
                  htmlFor="notify_on_failure"
                  className="text-sm font-medium text-[#F9FAFB]"
                >
                  Notificar em caso de falha
                </Label>
                <p className="mt-0.5 text-xs text-[#6B7280]">
                  Envia notificacao pelos canais de entrega quando a execucao falhar.
                </p>
              </div>
              <Controller
                name="notify_on_failure"
                control={control}
                render={({ field }) => (
                  <Switch
                    id="notify_on_failure"
                    checked={field.value}
                    onCheckedChange={field.onChange}
                    className="data-[state=checked]:bg-[#6366F1]"
                    aria-label="Notificar em caso de falha"
                  />
                )}
              />
            </div>
          </div>

          <Separator className="bg-[#2E3348]" />

          {/* Secao: Canais de entrega */}
          <div>
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-medium uppercase tracking-wider text-[#9CA3AF]">
                Canais de Entrega
              </h3>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={handleAddDeliveryConfig}
                className="border-[#2E3348] bg-transparent text-[#9CA3AF] hover:bg-[#2A2F42] hover:text-white"
              >
                <Plus className="size-3.5" />
                Adicionar Canal
              </Button>
            </div>

            {fields.length === 0 && (
              <div className="rounded-lg border border-dashed border-[#2E3348] p-6 text-center">
                <p className="text-sm text-[#6B7280]">
                  Nenhum canal de entrega configurado
                </p>
                <p className="mt-1 text-xs text-[#6B7280]">
                  Adicione um canal para receber os resultados da execução.
                </p>
              </div>
            )}

            <div className="space-y-4">
              {fields.map((field, index) => (
                <div
                  key={field.id}
                  className="rounded-lg border border-[#2E3348] bg-[#242838] p-4"
                >
                  <div className="mb-3 flex items-center justify-between">
                    <span className="text-sm font-medium text-[#F9FAFB]">
                      Canal {index + 1}
                    </span>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => remove(index)}
                      className="size-7 p-0 text-[#9CA3AF] hover:bg-[#EF4444]/10 hover:text-[#EF4444]"
                      aria-label={`Remover canal ${index + 1}`}
                    >
                      <Trash2 className="size-3.5" />
                    </Button>
                  </div>

                  <div className="space-y-3">
                    {/* Tipo do canal */}
                    <div>
                      <Label className="mb-1.5 text-xs font-medium text-[#9CA3AF]">
                        Tipo
                      </Label>
                      <Controller
                        name={`delivery_configs.${index}.channel_type`}
                        control={control}
                        render={({ field: selectField }) => (
                          <Select
                            value={selectField.value}
                            onValueChange={selectField.onChange}
                          >
                            <SelectTrigger className="w-full border-[#2E3348] bg-[#1A1D2E] text-[#F9FAFB] focus:border-[#6366F1] focus:ring-[#6366F1]">
                              <SelectValue placeholder="Tipo de canal" />
                            </SelectTrigger>
                            <SelectContent className="border-[#2E3348] bg-[#242838]">
                              <SelectItem
                                value="email"
                                className="text-[#F9FAFB] focus:bg-[#2A2F42] focus:text-[#F9FAFB]"
                              >
                                Email
                              </SelectItem>
                              <SelectItem
                                value="webhook"
                                className="text-[#F9FAFB] focus:bg-[#2A2F42] focus:text-[#F9FAFB]"
                              >
                                Webhook
                              </SelectItem>
                              <SelectItem
                                value="onedrive"
                                className="text-[#F9FAFB] focus:bg-[#2A2F42] focus:text-[#F9FAFB]"
                              >
                                OneDrive
                              </SelectItem>
                            </SelectContent>
                          </Select>
                        )}
                      />
                      {errors.delivery_configs?.[index]?.channel_type && (
                        <p
                          className="mt-1 text-xs text-[#EF4444]"
                          role="alert"
                        >
                          {
                            errors.delivery_configs[index].channel_type
                              ?.message
                          }
                        </p>
                      )}
                    </div>

                    {/* Destinatarios */}
                    <div>
                      <Label className="mb-1.5 text-xs font-medium text-[#9CA3AF]">
                        {watch(`delivery_configs.${index}.channel_type`) === 'webhook'
                          ? 'URLs de Webhook'
                          : 'Destinatários'}
                      </Label>
                      <Input
                        placeholder={
                          watch(`delivery_configs.${index}.channel_type`) === 'webhook'
                            ? 'https://api.exemplo.com/webhook'
                            : watch(`delivery_configs.${index}.channel_type`) === 'email'
                              ? 'email1@exemplo.com, email2@exemplo.com'
                              : 'pasta/destino'
                        }
                        className={cn(
                          'border-[#2E3348] bg-[#1A1D2E] text-[#F9FAFB] placeholder-[#6B7280] focus:border-[#6366F1] focus:ring-[#6366F1]',
                          errors.delivery_configs?.[index]?.recipients && 'border-[#EF4444] focus:border-[#EF4444] focus:ring-[#EF4444]'
                        )}
                        {...register(
                          `delivery_configs.${index}.recipients`
                        )}
                      />
                      {errors.delivery_configs?.[index]?.recipients ? (
                        <p
                          className="mt-1 text-xs text-[#EF4444]"
                          role="alert"
                        >
                          {
                            errors.delivery_configs[index].recipients
                              ?.message
                          }
                        </p>
                      ) : (
                        <p className="mt-1 text-xs text-[#6B7280]">
                          {watch(`delivery_configs.${index}.channel_type`) === 'email'
                            ? 'Separe múltiplos e-mails com vírgula.'
                            : watch(`delivery_configs.${index}.channel_type`) === 'webhook'
                              ? 'Informe a URL do webhook para receber os resultados.'
                              : 'Separe múltiplos destinatários com vírgula.'}
                        </p>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <DialogFooter className="gap-2 sm:gap-2">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              disabled={isSubmitting}
              className="border-[#2E3348] bg-transparent text-[#9CA3AF] hover:bg-[#2A2F42] hover:text-white"
            >
              Cancelar
            </Button>
            <Button
              type="submit"
              disabled={isSubmitting}
              className="bg-[#6366F1] text-white hover:bg-[#4F46E5]"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="size-4 animate-spin" />
                  Salvando...
                </>
              ) : isEditing ? (
                'Salvar Alterações'
              ) : (
                'Criar Job'
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
});

export { JobForm };
export type { JobFormProps };
