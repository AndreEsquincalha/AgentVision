import { useState, useCallback } from 'react';
import { Navigate } from 'react-router';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { Loader2, Eye, EyeOff } from 'lucide-react';

import { useAuth } from '@/hooks/useAuth';
import { ROUTES } from '@/utils/constants';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';

// --- Schema de validação ---

const loginSchema = z.object({
  email: z
    .string({ error: 'E-mail é obrigatório' })
    .min(1, 'E-mail é obrigatório')
    .email('E-mail inválido'),
  password: z
    .string({ error: 'Senha é obrigatória' })
    .min(6, 'Senha deve ter pelo menos 6 caracteres'),
});

type LoginFormData = z.infer<typeof loginSchema>;

// --- Componente Login ---

export default function Login() {
  const { isAuthenticated, isLoading: authLoading, login } = useAuth();
  const [showPassword, setShowPassword] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: '',
      password: '',
    },
  });

  const onSubmit = useCallback(
    async (data: LoginFormData) => {
      setLoginError(null);

      try {
        await login(data.email, data.password);
      } catch (error) {
        if (error instanceof Error) {
          setLoginError(error.message);
        } else {
          setLoginError('Ocorreu um erro ao fazer login. Tente novamente.');
        }
      }
    },
    [login]
  );

  const togglePasswordVisibility = useCallback(() => {
    setShowPassword((prev) => !prev);
  }, []);

  // Redireciona se já autenticado
  if (authLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-[#0F1117]">
        <Loader2 className="size-8 animate-spin text-[#6366F1]" />
      </div>
    );
  }

  if (isAuthenticated) {
    return <Navigate to={ROUTES.DASHBOARD} replace />;
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0F1117] p-4">
      <div className="w-full max-w-md">
        {/* Logo */}
        <div className="mb-8 text-center">
          <h1 className="bg-gradient-to-r from-[#6366F1] to-[#8B5CF6] bg-clip-text text-4xl font-bold text-transparent">
            AgentVision
          </h1>
          <p className="mt-2 text-sm text-[#9CA3AF]">
            Plataforma de automação com agentes de IA
          </p>
        </div>

        {/* Card de Login */}
        <Card className="border-[#2E3348] bg-[#1A1D2E]">
          <CardHeader className="text-center">
            <CardTitle className="text-xl text-[#F9FAFB]">
              Entrar na sua conta
            </CardTitle>
            <CardDescription className="text-[#9CA3AF]">
              Digite suas credenciais para acessar o painel
            </CardDescription>
          </CardHeader>

          <CardContent>
            <form onSubmit={handleSubmit(onSubmit)} noValidate>
              {/* Mensagem de erro global */}
              {loginError && (
                <div
                  className="mb-4 rounded-lg border border-[#EF4444]/20 bg-[#EF4444]/10 px-4 py-3 text-sm text-[#EF4444]"
                  role="alert"
                  aria-live="polite"
                >
                  {loginError}
                </div>
              )}

              {/* Campo E-mail */}
              <div className="mb-4">
                <Label
                  htmlFor="email"
                  className="mb-2 text-sm font-medium text-[#F9FAFB]"
                >
                  E-mail
                </Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="admin@agentvision.com"
                  autoComplete="email"
                  aria-invalid={errors.email ? 'true' : 'false'}
                  aria-describedby={errors.email ? 'email-error' : undefined}
                  className="mt-1 border-[#2E3348] bg-[#1A1D2E] text-[#F9FAFB] placeholder-[#6B7280] focus:border-[#6366F1] focus:ring-[#6366F1]"
                  {...register('email')}
                />
                {errors.email && (
                  <p
                    id="email-error"
                    className="mt-1 text-xs text-[#EF4444]"
                    role="alert"
                  >
                    {errors.email.message}
                  </p>
                )}
              </div>

              {/* Campo Senha */}
              <div className="mb-6">
                <Label
                  htmlFor="password"
                  className="mb-2 text-sm font-medium text-[#F9FAFB]"
                >
                  Senha
                </Label>
                <div className="relative mt-1">
                  <Input
                    id="password"
                    type={showPassword ? 'text' : 'password'}
                    placeholder="Digite sua senha"
                    autoComplete="current-password"
                    aria-invalid={errors.password ? 'true' : 'false'}
                    aria-describedby={
                      errors.password ? 'password-error' : undefined
                    }
                    className="border-[#2E3348] bg-[#1A1D2E] pr-10 text-[#F9FAFB] placeholder-[#6B7280] focus:border-[#6366F1] focus:ring-[#6366F1]"
                    {...register('password')}
                  />
                  <button
                    type="button"
                    onClick={togglePasswordVisibility}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-[#6B7280] hover:text-[#9CA3AF] focus:outline-none"
                    aria-label={
                      showPassword ? 'Ocultar senha' : 'Mostrar senha'
                    }
                    tabIndex={-1}
                  >
                    {showPassword ? (
                      <EyeOff className="size-4" />
                    ) : (
                      <Eye className="size-4" />
                    )}
                  </button>
                </div>
                {errors.password && (
                  <p
                    id="password-error"
                    className="mt-1 text-xs text-[#EF4444]"
                    role="alert"
                  >
                    {errors.password.message}
                  </p>
                )}
              </div>

              {/* Botão Entrar */}
              <Button
                type="submit"
                disabled={isSubmitting}
                className="w-full bg-[#6366F1] text-sm font-medium text-white hover:bg-[#4F46E5] disabled:opacity-50"
              >
                {isSubmitting ? (
                  <>
                    <Loader2 className="size-4 animate-spin" />
                    Entrando...
                  </>
                ) : (
                  'Entrar'
                )}
              </Button>
            </form>
          </CardContent>
        </Card>

        {/* Rodapé */}
        <p className="mt-6 text-center text-xs text-[#6B7280]">
          AgentVision v1.0 &mdash; Plataforma de automação
        </p>
      </div>
    </div>
  );
}
