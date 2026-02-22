import { memo, useState, useEffect } from 'react';
import { Outlet } from 'react-router';
import { Sidebar } from '@/components/layout/Sidebar';
import { Header } from '@/components/layout/Header';
import { STORAGE_KEYS } from '@/utils/constants';
import { cn } from '@/lib/utils';

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
 */
const MainLayout = memo(function MainLayout() {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(getSidebarCollapsed);

  // Escuta mudanças no localStorage para sincronizar com a Sidebar
  useEffect(() => {
    function handleStorageChange() {
      setSidebarCollapsed(getSidebarCollapsed());
    }

    // Usa MutationObserver no localStorage indiretamente via evento customizado
    // Verifica periodicamente (debounced) o estado do localStorage
    const interval = setInterval(handleStorageChange, 300);

    // Também escuta o evento de storage (funciona entre abas)
    window.addEventListener('storage', handleStorageChange);

    return () => {
      clearInterval(interval);
      window.removeEventListener('storage', handleStorageChange);
    };
  }, []);

  return (
    <div className="flex min-h-screen bg-[#0F1117]">
      {/* Sidebar fixa */}
      <Sidebar />

      {/* Área de conteúdo */}
      <div
        className={cn(
          'flex flex-1 flex-col transition-all duration-300',
          sidebarCollapsed ? 'ml-16' : 'ml-64'
        )}
      >
        {/* Header sticky */}
        <Header />

        {/* Conteúdo scrollável */}
        <main className="flex-1 overflow-y-auto p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
});

export { MainLayout };
