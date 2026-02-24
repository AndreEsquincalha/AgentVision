import { memo, useMemo } from 'react';
import { useLocation } from 'react-router';
import { useAuth } from '@/hooks/useAuth';
import { ROUTES } from '@/utils/constants';
import { cn } from '@/lib/utils';

// --- Mapeamento de rotas para títulos ---

const ROUTE_TITLES: Record<string, string> = {
  [ROUTES.DASHBOARD]: 'Dashboard',
  [ROUTES.PROJECTS]: 'Projetos',
  [ROUTES.JOBS]: 'Jobs',
  [ROUTES.EXECUTIONS]: 'Execuções',
  [ROUTES.PROMPTS]: 'Templates de Prompt',
  [ROUTES.SETTINGS]: 'Configurações',
};

/**
 * Resolve o título da página com base no pathname atual.
 * Trata rotas com parâmetros (ex: /projects/abc → "Detalhes do Projeto").
 */
function getPageTitle(pathname: string): string {
  // Correspondência exata
  if (ROUTE_TITLES[pathname]) {
    return ROUTE_TITLES[pathname];
  }

  // Correspondência por prefixo para rotas de detalhe
  if (pathname.startsWith('/projects/')) return 'Detalhes do Projeto';
  if (pathname.startsWith('/jobs/')) return 'Detalhes do Job';
  if (pathname.startsWith('/executions/')) return 'Detalhes da Execução';

  return 'AgentVision';
}

/**
 * Extrai as iniciais do nome do usuário (máximo 2 caracteres).
 * Ex: "João Silva" → "JS", "Admin" → "AD"
 */
function getInitials(name: string): string {
  if (!name) return '?';

  const parts = name.trim().split(/\s+/);
  if (parts.length >= 2) {
    return `${parts[0][0]}${parts[parts.length - 1][0]}`.toUpperCase();
  }

  return name.substring(0, 2).toUpperCase();
}

interface HeaderProps {
  /** Classes CSS adicionais */
  className?: string;
  /** Se está em modo mobile */
  isMobile?: boolean;
}

/**
 * Header fixo no topo da área de conteúdo.
 * Exibe o título dinâmico da página e informações do usuário.
 * Em mobile, adiciona padding à esquerda para o botão hamburger.
 */
const Header = memo(function Header({ className, isMobile = false }: HeaderProps) {
  const location = useLocation();
  const { user } = useAuth();

  const pageTitle = useMemo(
    () => getPageTitle(location.pathname),
    [location.pathname]
  );

  const initials = useMemo(
    () => getInitials(user?.name ?? ''),
    [user?.name]
  );

  return (
    <header
      className={cn(
        'sticky top-0 z-30 flex h-16 items-center justify-between border-b border-[#2E3348] bg-[#0F1117]/80 px-4 backdrop-blur-sm sm:px-6 lg:px-8',
        isMobile && 'pl-16',
        className
      )}
    >
      {/* Título da página */}
      <h2 className="truncate text-lg font-semibold text-[#F9FAFB] sm:text-xl">{pageTitle}</h2>

      {/* Informações do usuário */}
      {user && (
        <div className="flex shrink-0 items-center gap-3">
          <span className="hidden text-sm text-[#9CA3AF] sm:inline">{user.name}</span>
          <div
            className="flex size-8 items-center justify-center rounded-full bg-[#6366F1]/20 text-xs font-medium text-[#6366F1]"
            aria-label={`Avatar de ${user.name}`}
          >
            {initials}
          </div>
        </div>
      )}
    </header>
  );
});

export { Header };
