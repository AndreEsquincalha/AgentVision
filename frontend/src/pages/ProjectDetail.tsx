import { useState, useCallback, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router';
import {
  ArrowLeft,
  Pencil,
  Trash2,
  Globe,
  Cpu,
  KeyRound,
  CheckCircle2,
  XCircle,
  CalendarClock,
} from 'lucide-react';
import { useProject, useDeleteProject } from '@/hooks/useProjects';
import { ProjectForm } from '@/components/ProjectForm';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { Separator } from '@/components/ui/separator';
import { LLM_PROVIDERS, LLM_MODELS, ROUTES } from '@/utils/constants';
import { formatDateTime } from '@/utils/formatters';
import type { LLMProvider } from '@/types';

/**
 * Página de detalhes de um projeto.
 * Exibe informações gerais, configuração LLM, credenciais e jobs associados.
 */
export default function ProjectDetail() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  // --- Estado de dialogs ---
  const [formOpen, setFormOpen] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);

  // --- Query e mutation ---
  const { data: project, isPending, isError } = useProject(id ?? '');
  const deleteMutation = useDeleteProject();

  // --- Handlers ---

  const handleBack = useCallback(() => {
    navigate(ROUTES.PROJECTS);
  }, [navigate]);

  const handleEdit = useCallback(() => {
    setFormOpen(true);
  }, []);

  const handleDeleteClick = useCallback(() => {
    setDeleteDialogOpen(true);
  }, []);

  const handleConfirmDelete = useCallback(async () => {
    if (project) {
      try {
        await deleteMutation.mutateAsync(project.id);
        setDeleteDialogOpen(false);
        navigate(ROUTES.PROJECTS);
      } catch {
        // Erro tratado pelo hook (toast)
      }
    }
  }, [project, deleteMutation, navigate]);

  // Nome do modelo legível
  const modelName = useMemo(() => {
    if (!project) return '-';
    const model = LLM_MODELS.find((m) => m.id === project.llm_model);
    return model?.name ?? project.llm_model;
  }, [project]);

  // Provedor legível
  const providerName = useMemo(() => {
    if (!project) return '-';
    return (
      LLM_PROVIDERS[project.llm_provider as LLMProvider] ??
      project.llm_provider
    );
  }, [project]);

  // --- Loading state ---
  if (isPending) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-4">
          <Skeleton className="h-9 w-24" />
          <Skeleton className="h-8 w-64" />
        </div>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Skeleton className="h-64 w-full rounded-xl" />
          <Skeleton className="h-64 w-full rounded-xl" />
        </div>
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <Skeleton className="h-32 w-full rounded-xl" />
          <Skeleton className="h-32 w-full rounded-xl" />
        </div>
      </div>
    );
  }

  // --- Error / Not found state ---
  if (isError || !project) {
    return (
      <div className="space-y-6">
        <Button
          variant="ghost"
          onClick={handleBack}
          className="text-[#9CA3AF] hover:bg-[#2A2F42] hover:text-white"
        >
          <ArrowLeft className="size-4" />
          Voltar para Projetos
        </Button>
        <div className="rounded-xl border border-[#2E3348] bg-[#1A1D2E] p-12 text-center">
          <XCircle className="mx-auto mb-3 size-10 text-[#EF4444]" />
          <h2 className="text-lg font-semibold text-[#F9FAFB]">
            Projeto não encontrado
          </h2>
          <p className="mt-1 text-sm text-[#9CA3AF]">
            O projeto solicitado não existe ou foi removido.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Cabeçalho com botão voltar e ações */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="sm"
            onClick={handleBack}
            className="text-[#9CA3AF] hover:bg-[#2A2F42] hover:text-white"
            aria-label="Voltar para lista de projetos"
          >
            <ArrowLeft className="size-4" />
            Voltar
          </Button>
          <Separator orientation="vertical" className="h-6 bg-[#2E3348]" />
          <div>
            <h1 className="text-2xl font-semibold text-[#F9FAFB]">
              {project.name}
            </h1>
            <div className="mt-0.5 flex items-center gap-2">
              <span
                className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                  project.is_active
                    ? 'bg-[#10B981]/10 text-[#10B981]'
                    : 'bg-[#6B7280]/10 text-[#6B7280]'
                }`}
              >
                {project.is_active ? 'Ativo' : 'Inativo'}
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={handleEdit}
            className="border-[#2E3348] bg-transparent text-[#9CA3AF] hover:bg-[#2A2F42] hover:text-white"
          >
            <Pencil className="size-4" />
            Editar
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handleDeleteClick}
            className="border-[#2E3348] bg-transparent text-[#EF4444] hover:bg-[#EF4444]/10 hover:text-[#EF4444]"
          >
            <Trash2 className="size-4" />
            Excluir
          </Button>
        </div>
      </div>

      {/* Cards de informações */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Card: Informações Gerais */}
        <div className="rounded-xl border border-[#2E3348] bg-[#1A1D2E] p-6">
          <div className="mb-4 flex items-center gap-2">
            <Globe className="size-5 text-[#6366F1]" />
            <h2 className="text-base font-semibold text-[#F9FAFB]">
              Informações Gerais
            </h2>
          </div>

          <div className="space-y-4">
            <InfoRow label="Nome" value={project.name} />
            <InfoRow
              label="URL"
              value={
                <a
                  href={project.base_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[#818CF8] hover:text-[#6366F1] hover:underline"
                >
                  {project.base_url}
                </a>
              }
            />
            <InfoRow
              label="Descrição"
              value={project.description || 'Sem descrição'}
              muted={!project.description}
            />
            <InfoRow
              label="Criado em"
              value={formatDateTime(project.created_at)}
            />
            <InfoRow
              label="Atualizado em"
              value={formatDateTime(project.updated_at)}
            />
          </div>
        </div>

        {/* Card: Configuração LLM */}
        <div className="rounded-xl border border-[#2E3348] bg-[#1A1D2E] p-6">
          <div className="mb-4 flex items-center gap-2">
            <Cpu className="size-5 text-[#8B5CF6]" />
            <h2 className="text-base font-semibold text-[#F9FAFB]">
              Configuração LLM
            </h2>
          </div>

          <div className="space-y-4">
            <InfoRow label="Provider" value={providerName} />
            <InfoRow label="Modelo" value={modelName} />
            <InfoRow
              label="Temperatura"
              value={String(project.llm_temperature)}
            />
            <InfoRow
              label="Max Tokens"
              value={project.llm_max_tokens.toLocaleString('pt-BR')}
            />
            <InfoRow label="Timeout" value={`${project.llm_timeout}s`} />
            <InfoRow
              label="API Key"
              value={
                <span className="flex items-center gap-1.5">
                  {project.has_llm_api_key ? (
                    <>
                      <CheckCircle2 className="size-3.5 text-[#10B981]" />
                      <span className="text-[#10B981]">Configurada</span>
                    </>
                  ) : (
                    <>
                      <XCircle className="size-3.5 text-[#F59E0B]" />
                      <span className="text-[#F59E0B]">Não configurada</span>
                    </>
                  )}
                </span>
              }
            />
          </div>
        </div>
      </div>

      {/* Cards inferiores */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        {/* Card: Credenciais */}
        <div className="rounded-xl border border-[#2E3348] bg-[#1A1D2E] p-6">
          <div className="mb-4 flex items-center gap-2">
            <KeyRound className="size-5 text-[#22D3EE]" />
            <h2 className="text-base font-semibold text-[#F9FAFB]">
              Credenciais
            </h2>
          </div>

          <div className="space-y-4">
            <InfoRow
              label="Credenciais do site"
              value={
                <span className="flex items-center gap-1.5">
                  {project.has_credentials ? (
                    <>
                      <CheckCircle2 className="size-3.5 text-[#10B981]" />
                      <span className="text-[#10B981]">Configuradas</span>
                    </>
                  ) : (
                    <>
                      <XCircle className="size-3.5 text-[#6B7280]" />
                      <span className="text-[#6B7280]">Não configuradas</span>
                    </>
                  )}
                </span>
              }
            />
          </div>
        </div>

        {/* Card: Jobs Associados (placeholder) */}
        <div className="rounded-xl border border-[#2E3348] bg-[#1A1D2E] p-6">
          <div className="mb-4 flex items-center gap-2">
            <CalendarClock className="size-5 text-[#F59E0B]" />
            <h2 className="text-base font-semibold text-[#F9FAFB]">
              Jobs Associados
            </h2>
          </div>

          <div className="py-6 text-center">
            <CalendarClock className="mx-auto mb-2 size-8 text-[#6B7280]" />
            <p className="text-sm text-[#9CA3AF]">
              Nenhum job associado ainda
            </p>
            <p className="mt-1 text-xs text-[#6B7280]">
              Os jobs deste projeto aparecerão aqui quando forem criados.
            </p>
          </div>
        </div>
      </div>

      {/* Dialog de edição */}
      <ProjectForm
        open={formOpen}
        onOpenChange={setFormOpen}
        project={project}
      />

      {/* Dialog de confirmação de exclusão */}
      <ConfirmDialog
        open={deleteDialogOpen}
        onOpenChange={setDeleteDialogOpen}
        title="Excluir Projeto"
        description={`Tem certeza que deseja excluir o projeto "${project.name}"? Esta ação não pode ser desfeita. Todos os jobs e execuções associados também serão removidos.`}
        confirmLabel="Excluir"
        variant="danger"
        onConfirm={handleConfirmDelete}
        loading={deleteMutation.isPending}
      />
    </div>
  );
}

// --- Componente auxiliar: Linha de informação ---

interface InfoRowProps {
  label: string;
  value: React.ReactNode;
  muted?: boolean;
}

function InfoRow({ label, value, muted = false }: InfoRowProps) {
  return (
    <div className="flex items-start justify-between gap-4">
      <span className="shrink-0 text-sm text-[#9CA3AF]">{label}</span>
      <span
        className={`text-right text-sm ${
          muted ? 'text-[#6B7280]' : 'text-[#F9FAFB]'
        }`}
      >
        {value}
      </span>
    </div>
  );
}
