import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.shared.schemas import PaginatedResponse


class AuditLogResponse(BaseModel):
    """Schema de resposta de auditoria."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID | None = None
    action: str
    resource_type: str
    resource_id: str | None = None
    details: dict | None = None
    ip_address: str | None = None
    created_at: datetime
    updated_at: datetime


class AuditLogListParams(BaseModel):
    """Parametros de filtro (opcional)."""

    action: str | None = None
    resource_type: str | None = None
    user_id: uuid.UUID | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


AuditLogListResponse = PaginatedResponse[AuditLogResponse]
