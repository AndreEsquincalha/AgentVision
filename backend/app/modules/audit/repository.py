import uuid
from datetime import datetime

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.modules.audit.models import AuditLog


class AuditLogRepository:
    """
    Repositorio de logs de auditoria.
    """

    def __init__(self, db: Session) -> None:
        self._db = db

    def create(self, data: dict) -> AuditLog:
        """Cria um registro de auditoria."""
        log = AuditLog(**data)
        self._db.add(log)
        self._db.commit()
        self._db.refresh(log)
        return log

    def list(
        self,
        page: int = 1,
        per_page: int = 20,
        action: str | None = None,
        resource_type: str | None = None,
        user_id: uuid.UUID | None = None,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> tuple[list[AuditLog], int]:
        """Lista logs de auditoria com filtros e paginacao."""
        filters = []
        if action:
            filters.append(AuditLog.action == action)
        if resource_type:
            filters.append(AuditLog.resource_type == resource_type)
        if user_id:
            filters.append(AuditLog.user_id == user_id)
        if date_from:
            filters.append(AuditLog.created_at >= date_from)
        if date_to:
            filters.append(AuditLog.created_at <= date_to)

        stmt = select(AuditLog)
        if filters:
            stmt = stmt.where(and_(*filters))

        count_stmt = select(func.count()).select_from(AuditLog)
        if filters:
            count_stmt = count_stmt.where(and_(*filters))
        total = int(self._db.execute(count_stmt).scalar_one())

        stmt = stmt.order_by(AuditLog.created_at.desc())
        stmt = stmt.offset((page - 1) * per_page).limit(per_page)

        logs = list(self._db.execute(stmt).scalars().all())
        return logs, total
