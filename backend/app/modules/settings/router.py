from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.modules.auth.models import User
from app.modules.settings.repository import SettingRepository
from app.modules.settings.schemas import (
    SMTPConfigSchema,
    SettingsBulkUpdate,
    SettingsGroupResponse,
)
from app.modules.settings.service import SettingService
from app.shared.schemas import MessageResponse

router = APIRouter(
    prefix='/api/settings',
    tags=['Settings'],
)


# -------------------------------------------------------------------------
# Dependency injection chain: get_db -> repository -> service
# -------------------------------------------------------------------------


def get_setting_repository(
    db: Session = Depends(get_db),
) -> SettingRepository:
    """Dependency que fornece o repositorio de configuracoes."""
    return SettingRepository(db)


def get_setting_service(
    repository: SettingRepository = Depends(get_setting_repository),
) -> SettingService:
    """Dependency que fornece o servico de configuracoes."""
    return SettingService(repository)


# -------------------------------------------------------------------------
# Endpoints
# -------------------------------------------------------------------------

# IMPORTANTE: Rotas especificas (como /smtp/test) devem vir ANTES de rotas
# parametrizadas (como /{category}) para evitar conflitos de matching.


@router.post('/smtp/test', response_model=MessageResponse)
def test_smtp_connection(
    config: SMTPConfigSchema,
    current_user: User = Depends(get_current_user),
    service: SettingService = Depends(get_setting_service),
) -> MessageResponse:
    """
    Testa a conexao SMTP com as configuracoes fornecidas.

    Tenta conectar ao servidor SMTP, fazer login e desconectar.
    Retorna sucesso ou falha com mensagem explicativa.
    """
    success = service.test_smtp_connection(config)

    if success:
        return MessageResponse(
            success=True,
            message='Conexao SMTP estabelecida com sucesso',
        )
    else:
        return MessageResponse(
            success=False,
            message='Falha ao conectar ao servidor SMTP. Verifique as configuracoes.',
        )


@router.get('/{category}', response_model=SettingsGroupResponse)
def get_settings_by_category(
    category: str,
    current_user: User = Depends(get_current_user),
    service: SettingService = Depends(get_setting_service),
) -> SettingsGroupResponse:
    """
    Retorna todas as configuracoes de uma categoria com valores descriptografados.

    Categorias disponiveis: smtp, general.
    """
    return service.get_settings(category)


@router.put('/{category}', response_model=SettingsGroupResponse)
def update_settings_by_category(
    category: str,
    data: SettingsBulkUpdate,
    current_user: User = Depends(get_current_user),
    service: SettingService = Depends(get_setting_service),
) -> SettingsGroupResponse:
    """
    Atualiza configuracoes de uma categoria.

    Cada par chave-valor e criptografado e salvo (upsert).
    Se a chave ja existe, atualiza o valor. Caso contrario, cria nova entrada.
    """
    return service.update_settings(category, data.settings)
