import { memo } from 'react';
import type { ReactNode } from 'react';
import { cn } from '@/lib/utils';

interface PageHeaderProps {
  /** Título da página */
  title: string;
  /** Descrição opcional abaixo do título */
  description?: string;
  /** Elemento de ação à direita (ex: botão "Novo") */
  action?: ReactNode;
  /** Classes CSS adicionais */
  className?: string;
}

/**
 * Cabeçalho de página reutilizável.
 * Exibe título, descrição opcional e ação (botão) alinhada à direita.
 */
const PageHeader = memo(function PageHeader({
  title,
  description,
  action,
  className,
}: PageHeaderProps) {
  return (
    <div
      className={cn(
        'flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between',
        className
      )}
    >
      <div>
        <h1 className="text-2xl font-semibold text-[#F9FAFB]">{title}</h1>
        {description && (
          <p className="mt-1 text-sm text-[#9CA3AF]">{description}</p>
        )}
      </div>

      {action && <div className="mt-3 sm:mt-0">{action}</div>}
    </div>
  );
});

export { PageHeader };
export type { PageHeaderProps };
