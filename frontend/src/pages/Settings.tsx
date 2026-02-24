import { useCallback, useEffect, useMemo, useState } from 'react';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Loader2, CheckCircle2, Mail, Send } from 'lucide-react';
import { PageHeader } from '@/components/ui/PageHeader';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import { useSettings, useUpdateSettings, useTestSmtp } from '@/hooks/useSettings';
import { cn } from '@/lib/utils';
import type { SMTPConfig } from '@/types';

// --- Schema de validação SMTP ---

const smtpFormSchema = z.object({
  smtp_host: z
    .string({ error: 'Host é obrigatório' })
    .min(1, 'Host é obrigatório'),
  smtp_port: z
    .number({ error: 'Porta deve ser um número' })
    .int('Porta deve ser um número inteiro')
    .min(1, 'Porta deve ser maior que 0')
    .max(65535, 'Porta deve ser menor que 65536'),
  smtp_username: z.string().optional(),
  smtp_password: z.string().optional(),
  smtp_use_tls: z.boolean(),
  smtp_sender_email: z
    .string({ error: 'E-mail do remetente é obrigatório' })
    .min(1, 'E-mail do remetente é obrigatório')
    .email('E-mail inválido'),
});

type SMTPFormData = z.infer<typeof smtpFormSchema>;

/**
 * Página de Configurações.
 * Permite gerenciar configurações do sistema organizadas por seções.
 * Atualmente suporta configurações SMTP.
 */
export default function Settings() {
  const [activeSection] = useState<string>('smtp');

  // --- SMTP ---
  const {
    data: smtpSettings,
    isPending: isLoadingSmtp,
  } = useSettings('smtp');

  const updateMutation = useUpdateSettings();
  const testSmtpMutation = useTestSmtp();

  // Valores padrão do formulário SMTP
  const defaultValues = useMemo<SMTPFormData>(() => {
    if (!smtpSettings) {
      return {
        smtp_host: '',
        smtp_port: 587,
        smtp_username: '',
        smtp_password: '',
        smtp_use_tls: true,
        smtp_sender_email: '',
      };
    }

    return {
      smtp_host: smtpSettings['smtp_host'] || '',
      smtp_port: smtpSettings['smtp_port'] ? parseInt(smtpSettings['smtp_port'], 10) : 587,
      smtp_username: smtpSettings['smtp_username'] || '',
      smtp_password: '',
      smtp_use_tls: smtpSettings['smtp_use_tls'] === 'true',
      smtp_sender_email: smtpSettings['smtp_sender_email'] || '',
    };
  }, [smtpSettings]);

  const {
    register,
    handleSubmit,
    control,
    reset,
    getValues,
    formState: { errors, isDirty },
  } = useForm<SMTPFormData>({
    resolver: zodResolver(smtpFormSchema),
    defaultValues,
  });

  // Reseta o formulário quando as configurações carregam
  useEffect(() => {
    if (smtpSettings) {
      reset(defaultValues);
    }
  }, [smtpSettings, defaultValues, reset]);

  // Verifica se a senha já está configurada no backend
  const hasExistingPassword = useMemo(() => {
    if (!smtpSettings) return false;
    return !!smtpSettings['smtp_password'];
  }, [smtpSettings]);

  // Submissão do formulário SMTP
  const onSubmitSmtp = useCallback(
    async (data: SMTPFormData) => {
      // Backend espera dict[str, str] — converte tudo para string
      const payload: Record<string, string> = {
        smtp_host: data.smtp_host,
        smtp_port: String(data.smtp_port),
        smtp_use_tls: String(data.smtp_use_tls),
        smtp_sender_email: data.smtp_sender_email,
      };

      // Apenas envia username se preenchido
      if (data.smtp_username) {
        payload['smtp_username'] = data.smtp_username;
      }

      // Apenas envia senha se preenchida (campo novo ou alterado)
      if (data.smtp_password) {
        payload['smtp_password'] = data.smtp_password;
      }

      try {
        await updateMutation.mutateAsync({
          category: 'smtp',
          data: payload,
        });
      } catch {
        // Erro já tratado no hook (toast)
      }
    },
    [updateMutation]
  );

  // Teste de conexão SMTP
  const handleTestSmtp = useCallback(() => {
    const values = getValues();

    const config: SMTPConfig = {
      host: values.smtp_host,
      port: values.smtp_port,
      username: values.smtp_username || '',
      password: values.smtp_password || '',
      use_tls: values.smtp_use_tls,
      sender_email: values.smtp_sender_email,
    };

    testSmtpMutation.mutate(config);
  }, [getValues, testSmtpMutation]);

  // --- Seções do menu lateral ---

  const sections = useMemo(
    () => [
      {
        id: 'smtp',
        label: 'SMTP / E-mail',
        icon: Mail,
      },
    ],
    []
  );

  return (
    <div className="space-y-6">
      {/* Cabeçalho */}
      <PageHeader
        title="Configurações"
        description="Gerencie as configurações gerais do sistema."
      />

      <div className="flex flex-col gap-6 lg:flex-row">
        {/* Menu lateral de seções */}
        <nav
          className="w-full shrink-0 lg:w-56"
          aria-label="Seções de configuração"
        >
          <div className="rounded-xl border border-[#2E3348] bg-[#1A1D2E] p-2">
            {sections.map((section) => {
              const Icon = section.icon;
              const isActive = activeSection === section.id;
              return (
                <button
                  key={section.id}
                  className={`flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left text-sm font-medium transition-colors focus:outline-none focus-visible:ring-1 focus-visible:ring-[#6366F1] ${
                    isActive
                      ? 'bg-[#6366F1]/10 text-[#6366F1]'
                      : 'text-[#9CA3AF] hover:bg-[#2A2F42] hover:text-white'
                  }`}
                  aria-current={isActive ? 'page' : undefined}
                >
                  <Icon className="size-4" />
                  {section.label}
                </button>
              );
            })}
          </div>
        </nav>

        {/* Conteúdo da seção ativa */}
        <div className="flex-1">
          {activeSection === 'smtp' && (
            <div className="rounded-xl border border-[#2E3348] bg-[#1A1D2E] p-6">
              {/* Título da seção */}
              <div className="mb-6">
                <h2 className="flex items-center gap-2 text-lg font-semibold text-[#F9FAFB]">
                  <Mail className="size-5 text-[#6366F1]" />
                  Configurações SMTP
                </h2>
                <p className="mt-1 text-sm text-[#9CA3AF]">
                  Configure o servidor SMTP para envio de e-mails com relatórios
                  e notificações.
                </p>
              </div>

              <Separator className="mb-6 bg-[#2E3348]" />

              {/* Loading state */}
              {isLoadingSmtp ? (
                <div className="space-y-6">
                  {Array.from({ length: 6 }).map((_, i) => (
                    <div key={i} className="space-y-2">
                      <Skeleton className="h-4 w-24" />
                      <Skeleton className="h-10 w-full" />
                    </div>
                  ))}
                </div>
              ) : (
                <form
                  onSubmit={handleSubmit(onSubmitSmtp)}
                  className="space-y-6"
                >
                  {/* Servidor e Porta */}
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                    {/* Host */}
                    <div className="sm:col-span-2">
                      <Label
                        htmlFor="smtp_host"
                        className="mb-1.5 text-sm font-medium text-[#F9FAFB]"
                      >
                        Servidor SMTP *
                      </Label>
                      <Input
                        id="smtp_host"
                        placeholder="smtp.gmail.com"
                        aria-invalid={errors.smtp_host ? 'true' : 'false'}
                        aria-describedby={
                          errors.smtp_host ? 'smtp_host-error' : undefined
                        }
                        className={cn(
                          'border-[#2E3348] bg-[#242838] text-[#F9FAFB] placeholder-[#6B7280] focus:border-[#6366F1] focus:ring-[#6366F1]',
                          errors.smtp_host && 'border-[#EF4444] focus:border-[#EF4444] focus:ring-[#EF4444]'
                        )}
                        {...register('smtp_host')}
                      />
                      {errors.smtp_host && (
                        <p
                          id="smtp_host-error"
                          className="mt-1 text-xs text-[#EF4444]"
                          role="alert"
                        >
                          {errors.smtp_host.message}
                        </p>
                      )}
                    </div>

                    {/* Porta */}
                    <div>
                      <Label
                        htmlFor="smtp_port"
                        className="mb-1.5 text-sm font-medium text-[#F9FAFB]"
                      >
                        Porta *
                      </Label>
                      <Input
                        id="smtp_port"
                        type="number"
                        placeholder="587"
                        min="1"
                        max="65535"
                        aria-invalid={errors.smtp_port ? 'true' : 'false'}
                        aria-describedby={
                          errors.smtp_port ? 'smtp_port-error' : undefined
                        }
                        className={cn(
                          'border-[#2E3348] bg-[#242838] text-[#F9FAFB] placeholder-[#6B7280] focus:border-[#6366F1] focus:ring-[#6366F1]',
                          errors.smtp_port && 'border-[#EF4444] focus:border-[#EF4444] focus:ring-[#EF4444]'
                        )}
                        {...register('smtp_port', { valueAsNumber: true })}
                      />
                      {errors.smtp_port && (
                        <p
                          id="smtp_port-error"
                          className="mt-1 text-xs text-[#EF4444]"
                          role="alert"
                        >
                          {errors.smtp_port.message}
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Credenciais */}
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    {/* Usuário */}
                    <div>
                      <Label
                        htmlFor="smtp_username"
                        className="mb-1.5 text-sm font-medium text-[#F9FAFB]"
                      >
                        Usuário
                      </Label>
                      <Input
                        id="smtp_username"
                        placeholder="usuario@exemplo.com"
                        className="border-[#2E3348] bg-[#242838] text-[#F9FAFB] placeholder-[#6B7280] focus:border-[#6366F1] focus:ring-[#6366F1]"
                        {...register('smtp_username')}
                      />
                    </div>

                    {/* Senha */}
                    <div>
                      <Label
                        htmlFor="smtp_password"
                        className="mb-1.5 text-sm font-medium text-[#F9FAFB]"
                      >
                        Senha
                      </Label>
                      {hasExistingPassword && (
                        <p className="mb-1 text-xs text-[#9CA3AF]">
                          Senha já configurada. Preencha apenas para substituir.
                        </p>
                      )}
                      <Input
                        id="smtp_password"
                        type="password"
                        placeholder={
                          hasExistingPassword ? '••••••••' : 'Senha do SMTP'
                        }
                        className="border-[#2E3348] bg-[#242838] text-[#F9FAFB] placeholder-[#6B7280] focus:border-[#6366F1] focus:ring-[#6366F1]"
                        {...register('smtp_password')}
                      />
                    </div>
                  </div>

                  {/* E-mail do Remetente */}
                  <div>
                    <Label
                      htmlFor="smtp_sender_email"
                      className="mb-1.5 text-sm font-medium text-[#F9FAFB]"
                    >
                      E-mail do Remetente *
                    </Label>
                    <Input
                      id="smtp_sender_email"
                      type="email"
                      placeholder="noreply@meudominio.com"
                      aria-invalid={
                        errors.smtp_sender_email ? 'true' : 'false'
                      }
                      aria-describedby={
                        errors.smtp_sender_email
                          ? 'smtp_sender_email-error'
                          : undefined
                      }
                      className={cn(
                        'border-[#2E3348] bg-[#242838] text-[#F9FAFB] placeholder-[#6B7280] focus:border-[#6366F1] focus:ring-[#6366F1]',
                        errors.smtp_sender_email && 'border-[#EF4444] focus:border-[#EF4444] focus:ring-[#EF4444]'
                      )}
                      {...register('smtp_sender_email')}
                    />
                    {errors.smtp_sender_email && (
                      <p
                        id="smtp_sender_email-error"
                        className="mt-1 text-xs text-[#EF4444]"
                        role="alert"
                      >
                        {errors.smtp_sender_email.message}
                      </p>
                    )}
                  </div>

                  {/* TLS Toggle */}
                  <div className="flex items-center justify-between rounded-lg border border-[#2E3348] bg-[#242838] px-4 py-3">
                    <div>
                      <Label
                        htmlFor="smtp_use_tls"
                        className="text-sm font-medium text-[#F9FAFB]"
                      >
                        Usar TLS
                      </Label>
                      <p className="mt-0.5 text-xs text-[#9CA3AF]">
                        Ativa a criptografia TLS na conexão com o servidor SMTP.
                      </p>
                    </div>
                    <Controller
                      name="smtp_use_tls"
                      control={control}
                      render={({ field }) => (
                        <Switch
                          id="smtp_use_tls"
                          checked={field.value}
                          onCheckedChange={field.onChange}
                          aria-label="Ativar TLS"
                        />
                      )}
                    />
                  </div>

                  <Separator className="bg-[#2E3348]" />

                  {/* Botões de ação */}
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    {/* Testar conexão */}
                    <Button
                      type="button"
                      variant="outline"
                      onClick={handleTestSmtp}
                      disabled={testSmtpMutation.isPending}
                      className="border-[#2E3348] bg-transparent text-[#9CA3AF] hover:bg-[#2A2F42] hover:text-white"
                    >
                      {testSmtpMutation.isPending ? (
                        <>
                          <Loader2 className="size-4 animate-spin" />
                          Testando...
                        </>
                      ) : testSmtpMutation.isSuccess &&
                        testSmtpMutation.data?.success ? (
                        <>
                          <CheckCircle2 className="size-4 text-[#10B981]" />
                          Conexão OK
                        </>
                      ) : (
                        <>
                          <Send className="size-4" />
                          Testar Conexão
                        </>
                      )}
                    </Button>

                    {/* Salvar */}
                    <Button
                      type="submit"
                      disabled={updateMutation.isPending || !isDirty}
                      className="bg-[#6366F1] text-white hover:bg-[#4F46E5]"
                    >
                      {updateMutation.isPending ? (
                        <>
                          <Loader2 className="size-4 animate-spin" />
                          Salvando...
                        </>
                      ) : (
                        'Salvar Configurações'
                      )}
                    </Button>
                  </div>
                </form>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
