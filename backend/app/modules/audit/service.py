import uuid
from datetime import datetime

from app.modules.audit.repository import AuditLogRepository
from app.modules.audit.schemas import AuditLogResponse
from app.shared.schemas import PaginatedResponse


class AuditLogService:
    """
    Servico de auditoria.
    """

    def __init__(self, repository: AuditLogRepository) -> None:
        self._repository = repository

    def create_log(
        self,
        action: str,
        resource_type: str,
        resource_id: str | None,
        user_id: uuid.UUID | None,
        ip_address: str | None,
        details: dict | None = None,
    ) -> AuditLogResponse:
        """Cria um log de auditoria."""
        log = self._repository.create({
            'action': action,
            'resource_type': resource_type,
            'resource_id': resource_id,
            'user_id': user_id,
            'ip_address': ip_address,
            'details': details,
        })
        return AuditLogResponse.model_validate(log)

    def list_logs(
        self,
        page: int = 1,
        per_page: int = 20,
        action: str | None = None,
        resource_type: str | None = None,
        user_id: uuid.UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> PaginatedResponse[AuditLogResponse]:
        """Lista logs de auditoria com filtros."""
        logs, total = self._repository.list(
            page=page,
            per_page=per_page,
            action=action,
            resource_type=resource_type,
            user_id=user_id,
            date_from=date_from,
            date_to=date_to,
        )
        items = [AuditLogResponse.model_validate(log) for log in logs]
        return PaginatedResponse[AuditLogResponse].create(
            items=items,
            total=total,
            page=page,
            per_page=per_page,
        )
