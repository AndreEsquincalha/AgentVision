import { memo, useState, useEffect } from 'react';
import { Outlet } from 'react-router';
import { Sidebar } from '@/components/layout/Sidebar';
import { Header } from '@/components/layout/Header';
import { STORAGE_KEYS } from '@/utils/constants';
import { cn } from '@/lib/utils';

/** Breakpoint para considerar tela mobile */
const MOBILE_BREAKPOINT = 768;

/**
 * Lê o estado de colapso da sidebar do localStorage.
 * Usado para posicionar a área de conteúdo corretamente.
 */
function getSidebarCollapsed(): boolean {
  try {
    return localStorage.getItem(STORAGE_KEYS.SIDEBAR_COLLAPSED) === 'true';
  } catch {
    return false;
  }
}

/**
 * Layout principal da aplicação autenticada.
 * Combina Sidebar à esquerda e área de conteúdo com Header + Outlet.
 * A área de conteúdo se adapta ao estado da sidebar (colapsada/expandida).
 * Em mobile (< 768px), a sidebar vira overlay e o conteúdo ocupa toda a tela.
 */
const MainLayout = memo(function MainLayout() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(getSidebarCollapsed);
  const [isMobile, setIsMobile] = useState(false);

  // Detecta tela mobile
  useEffect(() => {
    function checkMobile() {
      setIsMobile(window.innerWidth < MOBILE_BREAKPOINT);
    }
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // Escuta mudanças no localStorage para sincronizar com a Sidebar
  useEffect(() => {
    function handleStorageChange() {
      setSidebarCollapsed(getSidebarCollapsed());
    }

    const interval = setInterval(handleStorageChange, 300);
    window.addEventListener('storage', handleStorageChange);

    return () => {
      clearInterval(interval);
      window.removeEventListener('storage', handleStorageChange);
    };
  }, []);

  return (
    <div className="flex min-h-screen bg-[#0F1117]">
      {/* Sidebar fixa (em mobile vira overlay) */}
      <Sidebar />

      {/* Área de conteúdo */}
      <div
        className={cn(
          'flex flex-1 flex-col transition-all duration-300',
          isMobile ? 'ml-0' : sidebarCollapsed ? 'ml-16' : 'ml-64'
        )}
      >
        {/* Header sticky */}
        <Header isMobile={isMobile} />

        {/* Conteúdo scrollável — padding menor em mobile */}
        <main className="flex-1 overflow-y-auto p-4 sm:p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
});

export { MainLayout };
