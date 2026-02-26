from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.modules.audit.repository import AuditLogRepository
from app.modules.audit.schemas import AuditLogListResponse
from app.modules.audit.service import AuditLogService

router = APIRouter(
    prefix='/api/audit-logs',
    tags=['Audit Logs'],
)


def get_audit_repository(db: Session = Depends(get_db)) -> AuditLogRepository:
    return AuditLogRepository(db)


def get_audit_service(
    repository: AuditLogRepository = Depends(get_audit_repository),
) -> AuditLogService:
    return AuditLogService(repository)


@router.get('', response_model=AuditLogListResponse)
def list_audit_logs(
    page: int = Query(1, ge=1, description='Numero da pagina'),
    per_page: int = Query(20, ge=1, le=100, description='Itens por pagina'),
    action: str | None = Query(None, description='Filtro por acao'),
    resource_type: str | None = Query(None, description='Filtro por tipo de recurso'),
    user_id: str | None = Query(None, description='Filtro por usuario (UUID)'),
    date_from: datetime | None = Query(None, description='Inicio do periodo'),
    date_to: datetime | None = Query(None, description='Fim do periodo'),
    service: AuditLogService = Depends(get_audit_service),
    current_user=Depends(require_roles('admin')),
) -> AuditLogListResponse:
    """Lista logs de auditoria (admin only)."""
    parsed_user_id = None
    if user_id:
        from uuid import UUID
        parsed_user_id = UUID(user_id)

    return service.list_logs(
        page=page,
        per_page=per_page,
        action=action,
        resource_type=resource_type,
        user_id=parsed_user_id,
        date_from=date_from,
        date_to=date_to,
    )
