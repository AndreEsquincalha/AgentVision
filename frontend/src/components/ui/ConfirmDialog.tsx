import { memo, useCallback } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';

interface ConfirmDialogProps {
  /** Se o dialog está aberto */
  open: boolean;
  /** Callback para abrir/fechar */
  onOpenChange: (open: boolean) => void;
  /** Título do dialog */
  title: string;
  /** Descrição/mensagem de confirmação */
  description: string;
  /** Label do botão de confirmação */
  confirmLabel?: string;
  /** Label do botão de cancelar */
  cancelLabel?: string;
  /** Variante visual (danger usa cor destrutiva) */
  variant?: 'default' | 'danger';
  /** Callback executado ao confirmar */
  onConfirm: () => void;
  /** Se o botão de confirmação está em loading */
  loading?: boolean;
}

/**
 * Modal de confirmação reutilizável.
 * Usado para confirmar ações destrutivas ou importantes.
 */
const ConfirmDialog = memo(function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = 'Confirmar',
  cancelLabel = 'Cancelar',
  variant = 'default',
  onConfirm,
  loading = false,
}: ConfirmDialogProps) {
  const handleCancel = useCallback(() => {
    onOpenChange(false);
  }, [onOpenChange]);

  const handleConfirm = useCallback(() => {
    onConfirm();
  }, [onConfirm]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="border-[#2E3348] bg-[#1A1D2E] sm:max-w-md"
        showCloseButton={false}
      >
        <DialogHeader>
          <DialogTitle className="text-lg font-semibold text-[#F9FAFB]">
            {title}
          </DialogTitle>
          <DialogDescription className="text-sm text-[#9CA3AF]">
            {description}
          </DialogDescription>
        </DialogHeader>

        <DialogFooter className="mt-2 gap-2 sm:gap-2">
          <Button
            variant="outline"
            onClick={handleCancel}
            disabled={loading}
            className="border-[#2E3348] bg-transparent text-[#9CA3AF] hover:bg-[#2A2F42] hover:text-white"
          >
            {cancelLabel}
          </Button>
          <Button
            onClick={handleConfirm}
            disabled={loading}
            className={
              variant === 'danger'
                ? 'bg-[#EF4444] text-white hover:bg-[#DC2626]'
                : 'bg-[#6366F1] text-white hover:bg-[#4F46E5]'
            }
          >
            {loading ? 'Aguarde...' : confirmLabel}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
});

export { ConfirmDialog };
export type { ConfirmDialogProps };
