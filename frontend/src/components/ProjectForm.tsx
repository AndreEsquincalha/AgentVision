import { memo, useCallback, useEffect, useMemo } from 'react';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Loader2 } from 'lucide-react';
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
import { useCreateProject, useUpdateProject } from '@/hooks/useProjects';
import { cn } from '@/lib/utils';
import {
  LLM_PROVIDERS,
  getModelsByProvider,
  DEFAULT_LLM_TEMPERATURE,
  DEFAULT_LLM_MAX_TOKENS,
  DEFAULT_LLM_TIMEOUT,
} from '@/utils/constants';
import type { Project, LLMProvider } from '@/types';

// --- Schema de validação ---

const projectFormSchema = z.object({
  name: z
    .string({ error: 'Nome é obrigatório' })
    .min(3, 'Nome deve ter pelo menos 3 caracteres'),
  base_url: z
    .string({ error: 'URL é obrigatória' })
    .min(1, 'URL é obrigatória')
    .url('URL inválida'),
  description: z.string().optional(),
  credentials_username: z.string().optional(),
  credentials_password: z.string().optional(),
  llm_provider: z.enum(['anthropic', 'openai', 'google', 'ollama'], {
    error: 'Provider é obrigatório',
  }),
  llm_model: z
    .string({ error: 'Modelo é obrigatório' })
    .min(1, 'Modelo é obrigatório'),
  llm_api_key: z.string().optional(),
  llm_temperature: z
    .number({ error: 'Temperatura deve ser um número' })
    .min(0, 'Temperatura mínima é 0')
    .max(2, 'Temperatura máxima é 2'),
  llm_max_tokens: z
    .number({ error: 'Max tokens deve ser um número' })
    .int('Max tokens deve ser inteiro')
    .min(1, 'Max tokens deve ser maior que 0'),
  llm_timeout: z
    .number({ error: 'Timeout deve ser um número' })
    .int('Timeout deve ser inteiro')
    .min(1, 'Timeout deve ser maior que 0'),
});

type ProjectFormData = z.infer<typeof projectFormSchema>;

// --- Props ---

interface ProjectFormProps {
  /** Se o dialog está aberto */
  open: boolean;
  /** Callback para abrir/fechar */
  onOpenChange: (open: boolean) => void;
  /** Projeto existente para edição (null = criação) */
  project?: Project | null;
}

/**
 * Formulário de criação/edição de projetos em formato modal (Dialog).
 * Usa react-hook-form + zod para validação e shadcn/ui para componentes.
 */
const ProjectForm = memo(function ProjectForm({
  open,
  onOpenChange,
  project,
}: ProjectFormProps) {
  const isEditing = !!project;
  const createMutation = useCreateProject();
  const updateMutation = useUpdateProject();
  const isSubmitting = createMutation.isPending || updateMutation.isPending;

  // Valores padrão do formulário
  const defaultValues = useMemo<ProjectFormData>(
    () => ({
      name: project?.name ?? '',
      base_url: project?.base_url ?? '',
      description: project?.description ?? '',
      credentials_username: '',
      credentials_password: '',
      llm_provider: project?.llm_provider ?? 'anthropic',
      llm_model: project?.llm_model ?? '',
      llm_api_key: '',
      llm_temperature: project?.llm_temperature ?? DEFAULT_LLM_TEMPERATURE,
      llm_max_tokens: project?.llm_max_tokens ?? DEFAULT_LLM_MAX_TOKENS,
      llm_timeout: project?.llm_timeout ?? DEFAULT_LLM_TIMEOUT,
    }),
    [project]
  );

  const {
    register,
    handleSubmit,
    control,
    watch,
    reset,
    setValue,
    formState: { errors },
  } = useForm<ProjectFormData>({
    resolver: zodResolver(projectFormSchema),
    defaultValues,
  });

  // Reseta o formulário quando o dialog abre/fecha ou o projeto muda
  useEffect(() => {
    if (open) {
      reset(defaultValues);
    }
  }, [open, defaultValues, reset]);

  // Observa o provider selecionado para atualizar os modelos disponíveis
  const selectedProvider = watch('llm_provider');
  const availableModels = useMemo(
    () => getModelsByProvider(selectedProvider),
    [selectedProvider]
  );

  // Quando o provider muda, limpa o modelo selecionado se não pertence ao novo provider
  useEffect(() => {
    const currentModel = watch('llm_model');
    const modelBelongsToProvider = availableModels.some(
      (m) => m.id === currentModel
    );
    if (!modelBelongsToProvider) {
      setValue('llm_model', availableModels[0]?.id ?? '');
    }
  }, [selectedProvider, availableModels, setValue, watch]);

  // Callback de submissão
  const onSubmit = useCallback(
    async (data: ProjectFormData) => {
      // Monta o payload para a API
      const payload = {
        name: data.name,
        base_url: data.base_url,
        description: data.description || undefined,
        credentials:
          data.credentials_username && data.credentials_password
            ? {
                username: data.credentials_username,
                password: data.credentials_password,
              }
            : undefined,
        llm_provider: data.llm_provider as LLMProvider,
        llm_model: data.llm_model,
        llm_api_key: data.llm_api_key || undefined,
        llm_temperature: data.llm_temperature,
        llm_max_tokens: data.llm_max_tokens,
        llm_timeout: data.llm_timeout,
      };

      try {
        if (isEditing && project) {
          await updateMutation.mutateAsync({ id: project.id, data: payload });
        } else {
          await createMutation.mutateAsync(payload);
        }
        onOpenChange(false);
      } catch {
        // Erro já tratado no hook (toast)
      }
    },
    [isEditing, project, createMutation, updateMutation, onOpenChange]
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto border-[#2E3348] bg-[#1A1D2E] sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="text-lg font-semibold text-[#F9FAFB]">
            {isEditing ? 'Editar Projeto' : 'Novo Projeto'}
          </DialogTitle>
          <DialogDescription className="text-sm text-[#9CA3AF]">
            {isEditing
              ? 'Atualize as informações do projeto.'
              : 'Preencha os dados para criar um novo projeto.'}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-6">
          {/* Seção: Dados básicos */}
          <div>
            <h3 className="mb-3 text-sm font-medium uppercase tracking-wider text-[#9CA3AF]">
              Dados Básicos
            </h3>
            <div className="space-y-4">
              {/* Nome */}
              <div>
                <Label
                  htmlFor="name"
                  className="mb-1.5 text-sm font-medium text-[#F9FAFB]"
                >
                  Nome *
                </Label>
                <Input
                  id="name"
                  placeholder="Meu Projeto"
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

              {/* URL Base */}
              <div>
                <Label
                  htmlFor="base_url"
                  className="mb-1.5 text-sm font-medium text-[#F9FAFB]"
                >
                  URL Base *
                </Label>
                <Input
                  id="base_url"
                  placeholder="https://exemplo.com"
                  aria-invalid={errors.base_url ? 'true' : 'false'}
                  aria-describedby={
                    errors.base_url ? 'base_url-error' : undefined
                  }
                  className={cn(
                    'border-[#2E3348] bg-[#242838] text-[#F9FAFB] placeholder-[#6B7280] focus:border-[#6366F1] focus:ring-[#6366F1]',
                    errors.base_url && 'border-[#EF4444] focus:border-[#EF4444] focus:ring-[#EF4444]'
                  )}
                  {...register('base_url')}
                />
                {errors.base_url ? (
                  <p
                    id="base_url-error"
                    className="mt-1 text-xs text-[#EF4444]"
                    role="alert"
                  >
                    {errors.base_url.message}
                  </p>
                ) : (
                  <p className="mt-1 text-xs text-[#6B7280]">
                    URL completa do site que será automatizado (incluindo https://).
                  </p>
                )}
              </div>

              {/* Descrição */}
              <div>
                <Label
                  htmlFor="description"
                  className="mb-1.5 text-sm font-medium text-[#F9FAFB]"
                >
                  Descrição
                </Label>
                <Textarea
                  id="description"
                  placeholder="Descrição do projeto (opcional)"
                  rows={3}
                  className="border-[#2E3348] bg-[#242838] text-[#F9FAFB] placeholder-[#6B7280] focus:border-[#6366F1] focus:ring-[#6366F1]"
                  {...register('description')}
                />
              </div>
            </div>
          </div>

          <Separator className="bg-[#2E3348]" />

          {/* Seção: Credenciais do site alvo */}
          <div>
            <h3 className="mb-3 text-sm font-medium uppercase tracking-wider text-[#9CA3AF]">
              Credenciais do Site
            </h3>
            {isEditing && project?.has_credentials && (
              <p className="mb-3 text-xs text-[#9CA3AF]">
                Este projeto possui credenciais salvas. Preencha os campos
                abaixo apenas se deseja substituí-las.
              </p>
            )}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              {/* Usuário */}
              <div>
                <Label
                  htmlFor="credentials_username"
                  className="mb-1.5 text-sm font-medium text-[#F9FAFB]"
                >
                  Usuário
                </Label>
                <Input
                  id="credentials_username"
                  autoComplete="off"
                  placeholder={
                    isEditing && project?.has_credentials
                      ? '••••••••'
                      : 'Usuário do site'
                  }
                  className="border-[#2E3348] bg-[#242838] text-[#F9FAFB] placeholder-[#6B7280] focus:border-[#6366F1] focus:ring-[#6366F1]"
                  {...register('credentials_username')}
                />
              </div>

              {/* Senha */}
              <div>
                <Label
                  htmlFor="credentials_password"
                  className="mb-1.5 text-sm font-medium text-[#F9FAFB]"
                >
                  Senha
                </Label>
                <Input
                  id="credentials_password"
                  type="password"
                  autoComplete="new-password"
                  placeholder={
                    isEditing && project?.has_credentials
                      ? '••••••••'
                      : 'Senha do site'
                  }
                  className="border-[#2E3348] bg-[#242838] text-[#F9FAFB] placeholder-[#6B7280] focus:border-[#6366F1] focus:ring-[#6366F1]"
                  {...register('credentials_password')}
                />
              </div>
            </div>
          </div>

          <Separator className="bg-[#2E3348]" />

          {/* Seção: Configuração LLM */}
          <div>
            <h3 className="mb-3 text-sm font-medium uppercase tracking-wider text-[#9CA3AF]">
              Configuração LLM
            </h3>
            <div className="space-y-4">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                {/* Provider */}
                <div>
                  <Label
                    htmlFor="llm_provider"
                    className="mb-1.5 text-sm font-medium text-[#F9FAFB]"
                  >
                    Provider *
                  </Label>
                  <Controller
                    name="llm_provider"
                    control={control}
                    render={({ field }) => (
                      <Select
                        value={field.value}
                        onValueChange={field.onChange}
                      >
                        <SelectTrigger
                          id="llm_provider"
                          className="w-full border-[#2E3348] bg-[#242838] text-[#F9FAFB] focus:border-[#6366F1] focus:ring-[#6366F1]"
                          aria-invalid={
                            errors.llm_provider ? 'true' : 'false'
                          }
                        >
                          <SelectValue placeholder="Selecione o provider" />
                        </SelectTrigger>
                        <SelectContent className="border-[#2E3348] bg-[#242838]">
                          {(
                            Object.entries(LLM_PROVIDERS) as [
                              LLMProvider,
                              string,
                            ][]
                          ).map(([value, label]) => (
                            <SelectItem
                              key={value}
                              value={value}
                              className="text-[#F9FAFB] focus:bg-[#2A2F42] focus:text-[#F9FAFB]"
                            >
                              {label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  />
                  {errors.llm_provider && (
                    <p className="mt-1 text-xs text-[#EF4444]" role="alert">
                      {errors.llm_provider.message}
                    </p>
                  )}
                </div>

                {/* Modelo */}
                <div>
                  <Label
                    htmlFor="llm_model"
                    className="mb-1.5 text-sm font-medium text-[#F9FAFB]"
                  >
                    Modelo *
                  </Label>
                  <Controller
                    name="llm_model"
                    control={control}
                    render={({ field }) => (
                      <Select
                        value={field.value}
                        onValueChange={field.onChange}
                      >
                        <SelectTrigger
                          id="llm_model"
                          className="w-full border-[#2E3348] bg-[#242838] text-[#F9FAFB] focus:border-[#6366F1] focus:ring-[#6366F1]"
                          aria-invalid={errors.llm_model ? 'true' : 'false'}
                        >
                          <SelectValue placeholder="Selecione o modelo" />
                        </SelectTrigger>
                        <SelectContent className="border-[#2E3348] bg-[#242838]">
                          {availableModels.map((model) => (
                            <SelectItem
                              key={model.id}
                              value={model.id}
                              className="text-[#F9FAFB] focus:bg-[#2A2F42] focus:text-[#F9FAFB]"
                            >
                              {model.name}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  />
                  {errors.llm_model && (
                    <p className="mt-1 text-xs text-[#EF4444]" role="alert">
                      {errors.llm_model.message}
                    </p>
                  )}
                </div>
              </div>

              {/* API Key */}
              <div>
                <Label
                  htmlFor="llm_api_key"
                  className="mb-1.5 text-sm font-medium text-[#F9FAFB]"
                >
                  API Key
                </Label>
                {isEditing && project?.has_llm_api_key && (
                  <p className="mb-1 text-xs text-[#9CA3AF]">
                    Chave de API já configurada. Preencha apenas para
                    substituir.
                  </p>
                )}
                <Input
                  id="llm_api_key"
                  type="password"
                  placeholder={
                    isEditing && project?.has_llm_api_key
                      ? '••••••••'
                      : 'Chave de API do provider'
                  }
                  className="border-[#2E3348] bg-[#242838] text-[#F9FAFB] placeholder-[#6B7280] focus:border-[#6366F1] focus:ring-[#6366F1]"
                  {...register('llm_api_key')}
                />
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                {/* Temperatura */}
                <div>
                  <Label
                    htmlFor="llm_temperature"
                    className="mb-1.5 text-sm font-medium text-[#F9FAFB]"
                  >
                    Temperatura
                  </Label>
                  <Input
                    id="llm_temperature"
                    type="number"
                    step="0.1"
                    min="0"
                    max="2"
                    aria-invalid={
                      errors.llm_temperature ? 'true' : 'false'
                    }
                    className="border-[#2E3348] bg-[#242838] text-[#F9FAFB] placeholder-[#6B7280] focus:border-[#6366F1] focus:ring-[#6366F1]"
                    {...register('llm_temperature', { valueAsNumber: true })}
                  />
                  {errors.llm_temperature && (
                    <p className="mt-1 text-xs text-[#EF4444]" role="alert">
                      {errors.llm_temperature.message}
                    </p>
                  )}
                </div>

                {/* Max Tokens */}
                <div>
                  <Label
                    htmlFor="llm_max_tokens"
                    className="mb-1.5 text-sm font-medium text-[#F9FAFB]"
                  >
                    Max Tokens
                  </Label>
                  <Input
                    id="llm_max_tokens"
                    type="number"
                    min="1"
                    aria-invalid={
                      errors.llm_max_tokens ? 'true' : 'false'
                    }
                    className="border-[#2E3348] bg-[#242838] text-[#F9FAFB] placeholder-[#6B7280] focus:border-[#6366F1] focus:ring-[#6366F1]"
                    {...register('llm_max_tokens', { valueAsNumber: true })}
                  />
                  {errors.llm_max_tokens && (
                    <p className="mt-1 text-xs text-[#EF4444]" role="alert">
                      {errors.llm_max_tokens.message}
                    </p>
                  )}
                </div>

                {/* Timeout */}
                <div>
                  <Label
                    htmlFor="llm_timeout"
                    className="mb-1.5 text-sm font-medium text-[#F9FAFB]"
                  >
                    Timeout (s)
                  </Label>
                  <Input
                    id="llm_timeout"
                    type="number"
                    min="1"
                    aria-invalid={errors.llm_timeout ? 'true' : 'false'}
                    className="border-[#2E3348] bg-[#242838] text-[#F9FAFB] placeholder-[#6B7280] focus:border-[#6366F1] focus:ring-[#6366F1]"
                    {...register('llm_timeout', { valueAsNumber: true })}
                  />
                  {errors.llm_timeout && (
                    <p className="mt-1 text-xs text-[#EF4444]" role="alert">
                      {errors.llm_timeout.message}
                    </p>
                  )}
                </div>
              </div>
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
                'Criar Projeto'
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
});

export { ProjectForm };
export type { ProjectFormProps };
