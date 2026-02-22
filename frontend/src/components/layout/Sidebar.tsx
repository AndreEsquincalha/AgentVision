import { useState, useCallback, useMemo, memo } from 'react';
import { useLocation, useNavigate } from 'react-router';
import {
  LayoutDashboard,
  FolderKanban,
  Briefcase,
  Play,
  FileText,
  Settings,
  LogOut,
  ChevronLeft,
  ChevronRight,
  Eye,
} from 'lucide-react';
import { useAuth } from '@/hooks/useAuth';
import { ROUTES, STORAGE_KEYS } from '@/utils/constants';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { cn } from '@/lib/utils';

// --- Definição dos itens de navegação ---

interface NavItem {
  label: string;
  icon: React.ComponentType<React.SVGProps<SVGSVGElement> & { className?: string }>;
  route: string;
}

const NAV_ITEMS: NavItem[] = [
  { label: 'Dashboard', icon: LayoutDashboard, route: ROUTES.DASHBOARD },
  { label: 'Projetos', icon: FolderKanban, route: ROUTES.PROJECTS },
  { label: 'Jobs', icon: Briefcase, route: ROUTES.JOBS },
  { label: 'Execuções', icon: Play, route: ROUTES.EXECUTIONS },
  { label: 'Templates', icon: FileText, route: ROUTES.PROMPTS },
  { label: 'Configurações', icon: Settings, route: ROUTES.SETTINGS },
];

/**
 * Lê o estado de colapso da sidebar do localStorage.
 */
function getInitialCollapsed(): boolean {
  try {
    const stored = localStorage.getItem(STORAGE_KEYS.SIDEBAR_COLLAPSED);
    return stored === 'true';
  } catch {
    return false;
  }
}

/**
 * Sidebar fixa à esquerda com navegação principal.
 * Suporta estado colapsado (64px) e expandido (256px).
 * O estado é persistido no localStorage.
 */
const Sidebar = memo(function Sidebar() {
  const [collapsed, setCollapsed] = useState(getInitialCollapsed);
  const location = useLocation();
  const navigate = useNavigate();
  const { logout } = useAuth();

  const toggleCollapsed = useCallback(() => {
    setCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(STORAGE_KEYS.SIDEBAR_COLLAPSED, String(next));
      } catch {
        // Ignora erros de localStorage
      }
      return next;
    });
  }, []);

  const handleNavigation = useCallback(
    (route: string) => {
      navigate(route);
    },
    [navigate]
  );

  const handleLogout = useCallback(() => {
    logout();
    navigate(ROUTES.LOGIN);
  }, [logout, navigate]);

  /**
   * Verifica se um item de navegação está ativo com base na rota atual.
   */
  const isActive = useCallback(
    (route: string): boolean => {
      // Correspondência exata para dashboard
      if (route === ROUTES.DASHBOARD) {
        return location.pathname === ROUTES.DASHBOARD;
      }
      // Correspondência por prefixo para outras rotas
      return location.pathname.startsWith(route);
    },
    [location.pathname]
  );

  const navItemElements = useMemo(
    () =>
      NAV_ITEMS.map((item) => {
        const active = isActive(item.route);
        const Icon = item.icon;

        const button = (
          <button
            key={item.route}
            onClick={() => handleNavigation(item.route)}
            className={cn(
              'flex w-full items-center gap-3 rounded-lg px-4 py-2.5 text-sm transition-colors',
              active
                ? 'bg-[#6366F1]/10 font-medium text-[#6366F1]'
                : 'text-[#9CA3AF] hover:bg-[#2A2F42] hover:text-white',
              collapsed && 'justify-center px-0'
            )}
            aria-label={item.label}
            aria-current={active ? 'page' : undefined}
          >
            <Icon className="size-5 shrink-0" />
            {!collapsed && <span>{item.label}</span>}
          </button>
        );

        // Mostra tooltip quando colapsado
        if (collapsed) {
          return (
            <Tooltip key={item.route}>
              <TooltipTrigger asChild>{button}</TooltipTrigger>
              <TooltipContent side="right" className="bg-[#242838] text-[#F9FAFB]">
                {item.label}
              </TooltipContent>
            </Tooltip>
          );
        }

        return button;
      }),
    [isActive, handleNavigation, collapsed]
  );

  return (
    <aside
      className={cn(
        'fixed left-0 top-0 z-40 flex h-screen flex-col border-r border-[#2E3348] bg-[#1A1D2E] transition-all duration-300',
        collapsed ? 'w-16' : 'w-64'
      )}
      role="navigation"
      aria-label="Navegação principal"
    >
      {/* Logo */}
      <div
        className={cn(
          'flex items-center border-b border-[#2E3348] px-6 py-5',
          collapsed && 'justify-center px-3'
        )}
      >
        {collapsed ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <div className="flex items-center justify-center">
                <Eye className="size-6 text-[#6366F1]" />
              </div>
            </TooltipTrigger>
            <TooltipContent side="right" className="bg-[#242838] text-[#F9FAFB]">
              AgentVision
            </TooltipContent>
          </Tooltip>
        ) : (
          <div className="flex items-center gap-2.5">
            <Eye className="size-6 text-[#6366F1]" />
            <span className="bg-gradient-to-r from-[#6366F1] to-[#8B5CF6] bg-clip-text text-lg font-bold text-transparent">
              AgentVision
            </span>
          </div>
        )}
      </div>

      {/* Navegação */}
      <nav className="flex-1 space-y-1 overflow-y-auto px-2 py-4">
        {navItemElements}
      </nav>

      {/* Área inferior — logout e colapsar */}
      <div className="border-t border-[#2E3348] px-2 py-3 space-y-1">
        {/* Botão de logout */}
        {collapsed ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                onClick={handleLogout}
                className="flex w-full items-center justify-center rounded-lg px-4 py-2.5 text-sm text-[#9CA3AF] transition-colors hover:bg-[#2A2F42] hover:text-[#EF4444]"
                aria-label="Sair"
              >
                <LogOut className="size-5" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="right" className="bg-[#242838] text-[#F9FAFB]">
              Sair
            </TooltipContent>
          </Tooltip>
        ) : (
          <button
            onClick={handleLogout}
            className="flex w-full items-center gap-3 rounded-lg px-4 py-2.5 text-sm text-[#9CA3AF] transition-colors hover:bg-[#2A2F42] hover:text-[#EF4444]"
            aria-label="Sair"
          >
            <LogOut className="size-5" />
            <span>Sair</span>
          </button>
        )}

        {/* Botão de colapsar */}
        {collapsed ? (
          <Tooltip>
            <TooltipTrigger asChild>
              <button
                onClick={toggleCollapsed}
                className="flex w-full items-center justify-center rounded-lg px-4 py-2.5 text-sm text-[#9CA3AF] transition-colors hover:bg-[#2A2F42] hover:text-white"
                aria-label="Expandir sidebar"
              >
                <ChevronRight className="size-5" />
              </button>
            </TooltipTrigger>
            <TooltipContent side="right" className="bg-[#242838] text-[#F9FAFB]">
              Expandir
            </TooltipContent>
          </Tooltip>
        ) : (
          <button
            onClick={toggleCollapsed}
            className="flex w-full items-center gap-3 rounded-lg px-4 py-2.5 text-sm text-[#9CA3AF] transition-colors hover:bg-[#2A2F42] hover:text-white"
            aria-label="Colapsar sidebar"
          >
            <ChevronLeft className="size-5" />
            <span>Colapsar</span>
          </button>
        )}
      </div>
    </aside>
  );
});

export { Sidebar };
