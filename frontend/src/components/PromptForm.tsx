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
import { useCreatePrompt, useUpdatePrompt } from '@/hooks/usePrompts';
import { cn } from '@/lib/utils';
import { PROMPT_CATEGORIES } from '@/utils/constants';
import type { PromptTemplate } from '@/types';

// --- Schema de validação ---

const promptFormSchema = z.object({
  name: z
    .string({ error: 'Nome é obrigatório' })
    .min(3, 'Nome deve ter pelo menos 3 caracteres'),
  category: z.string().optional(),
  description: z.string().optional(),
  content: z
    .string({ error: 'Conteúdo do prompt é obrigatório' })
    .min(10, 'O conteúdo deve ter pelo menos 10 caracteres'),
});

type PromptFormData = z.infer<typeof promptFormSchema>;

// --- Props ---

interface PromptFormProps {
  /** Se o dialog está aberto */
  open: boolean;
  /** Callback para abrir/fechar */
  onOpenChange: (open: boolean) => void;
  /** Template existente para edição (null = criação) */
  prompt?: PromptTemplate | null;
}

/**
 * Formulário de criação/edição de templates de prompt em formato modal (Dialog).
 * Usa react-hook-form + zod para validação e shadcn/ui para componentes.
 */
const PromptForm = memo(function PromptForm({
  open,
  onOpenChange,
  prompt,
}: PromptFormProps) {
  const isEditing = !!prompt;
  const createMutation = useCreatePrompt();
  const updateMutation = useUpdatePrompt();
  const isSubmitting = createMutation.isPending || updateMutation.isPending;

  // Valores padrão do formulário
  const defaultValues = useMemo<PromptFormData>(
    () => ({
      name: prompt?.name ?? '',
      category: prompt?.category ?? '',
      description: prompt?.description ?? '',
      content: prompt?.content ?? '',
    }),
    [prompt]
  );

  const {
    register,
    handleSubmit,
    control,
    reset,
    formState: { errors },
  } = useForm<PromptFormData>({
    resolver: zodResolver(promptFormSchema),
    defaultValues,
  });

  // Reseta o formulário quando o dialog abre/fecha ou o template muda
  useEffect(() => {
    if (open) {
      reset(defaultValues);
    }
  }, [open, defaultValues, reset]);

  // Callback de submissão
  const onSubmit = useCallback(
    async (data: PromptFormData) => {
      const payload = {
        name: data.name,
        content: data.content,
        description: data.description || undefined,
        category: data.category || undefined,
      };

      try {
        if (isEditing && prompt) {
          await updateMutation.mutateAsync({ id: prompt.id, data: payload });
        } else {
          await createMutation.mutateAsync(payload);
        }
        onOpenChange(false);
      } catch {
        // Erro já tratado no hook (toast)
      }
    },
    [isEditing, prompt, createMutation, updateMutation, onOpenChange]
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] overflow-y-auto border-[#2E3348] bg-[#1A1D2E] sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle className="text-lg font-semibold text-[#F9FAFB]">
            {isEditing ? 'Editar Template' : 'Novo Template'}
          </DialogTitle>
          <DialogDescription className="text-sm text-[#9CA3AF]">
            {isEditing
              ? 'Atualize as informações do template de prompt.'
              : 'Preencha os dados para criar um novo template de prompt.'}
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
          {/* Nome */}
          <div>
            <Label
              htmlFor="prompt-name"
              className="mb-1.5 text-sm font-medium text-[#F9FAFB]"
            >
              Nome *
            </Label>
            <Input
              id="prompt-name"
              placeholder="Nome do template"
              aria-invalid={errors.name ? 'true' : 'false'}
              aria-describedby={errors.name ? 'prompt-name-error' : undefined}
              className={cn(
                'border-[#2E3348] bg-[#242838] text-[#F9FAFB] placeholder-[#6B7280] focus:border-[#6366F1] focus:ring-[#6366F1]',
                errors.name && 'border-[#EF4444] focus:border-[#EF4444] focus:ring-[#EF4444]'
              )}
              {...register('name')}
            />
            {errors.name && (
              <p
                id="prompt-name-error"
                className="mt-1 text-xs text-[#EF4444]"
                role="alert"
              >
                {errors.name.message}
              </p>
            )}
          </div>

          {/* Categoria */}
          <div>
            <Label
              htmlFor="prompt-category"
              className="mb-1.5 text-sm font-medium text-[#F9FAFB]"
            >
              Categoria
            </Label>
            <Controller
              name="category"
              control={control}
              render={({ field }) => (
                <Select
                  value={field.value || ''}
                  onValueChange={(value) =>
                    field.onChange(value === '__none__' ? '' : value)
                  }
                >
                  <SelectTrigger
                    id="prompt-category"
                    className="w-full border-[#2E3348] bg-[#242838] text-[#F9FAFB] focus:border-[#6366F1] focus:ring-[#6366F1]"
                  >
                    <SelectValue placeholder="Selecione uma categoria" />
                  </SelectTrigger>
                  <SelectContent className="border-[#2E3348] bg-[#242838]">
                    <SelectItem
                      value="__none__"
                      className="text-[#9CA3AF] focus:bg-[#2A2F42] focus:text-[#F9FAFB]"
                    >
                      Nenhuma
                    </SelectItem>
                    {PROMPT_CATEGORIES.map((cat) => (
                      <SelectItem
                        key={cat.value}
                        value={cat.value}
                        className="text-[#F9FAFB] focus:bg-[#2A2F42] focus:text-[#F9FAFB]"
                      >
                        {cat.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
          </div>

          {/* Descrição */}
          <div>
            <Label
              htmlFor="prompt-description"
              className="mb-1.5 text-sm font-medium text-[#F9FAFB]"
            >
              Descrição
            </Label>
            <Textarea
              id="prompt-description"
              placeholder="Descrição do template (opcional)"
              rows={2}
              className="border-[#2E3348] bg-[#242838] text-[#F9FAFB] placeholder-[#6B7280] focus:border-[#6366F1] focus:ring-[#6366F1]"
              {...register('description')}
            />
          </div>

          {/* Conteúdo do prompt */}
          <div>
            <Label
              htmlFor="prompt-content"
              className="mb-1.5 text-sm font-medium text-[#F9FAFB]"
            >
              Conteúdo do Prompt *
            </Label>
            <Textarea
              id="prompt-content"
              placeholder="Digite o conteúdo do prompt aqui. Use {{variavel}} para variáveis dinâmicas."
              rows={10}
              aria-invalid={errors.content ? 'true' : 'false'}
              aria-describedby={
                errors.content ? 'prompt-content-error' : undefined
              }
              className={cn(
                'min-h-[200px] border-[#2E3348] bg-[#242838] font-mono text-sm text-[#F9FAFB] placeholder-[#6B7280] focus:border-[#6366F1] focus:ring-[#6366F1]',
                errors.content && 'border-[#EF4444] focus:border-[#EF4444] focus:ring-[#EF4444]'
              )}
              {...register('content')}
            />
            {errors.content && (
              <p
                id="prompt-content-error"
                className="mt-1 text-xs text-[#EF4444]"
                role="alert"
              >
                {errors.content.message}
              </p>
            )}
          </div>

          {/* Versão (somente leitura em edição) */}
          {isEditing && prompt && (
            <div className="flex items-center gap-2 rounded-lg border border-[#2E3348] bg-[#242838] px-4 py-2.5">
              <span className="text-xs font-medium uppercase tracking-wider text-[#9CA3AF]">
                Versão atual:
              </span>
              <span className="text-sm font-semibold text-[#F9FAFB]">
                v{prompt.version}
              </span>
              <span className="text-xs text-[#6B7280]">
                (a versão será incrementada ao salvar)
              </span>
            </div>
          )}

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
                'Criar Template'
              )}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
});

export { PromptForm };
export type { PromptFormProps };
