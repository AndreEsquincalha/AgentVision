/**
 * Componente raiz da aplicação AgentVision.
 * As rotas, providers e layout serão configurados nos próximos sprints.
 */
function App() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#0F1117]">
      <div className="text-center">
        <h1 className="bg-gradient-to-r from-[#6366F1] to-[#8B5CF6] bg-clip-text text-4xl font-bold text-transparent">
          AgentVision
        </h1>
        <p className="mt-4 text-sm text-[#9CA3AF]">
          Plataforma de automação com agentes de IA
        </p>
      </div>
    </div>
  )
}

export default App
