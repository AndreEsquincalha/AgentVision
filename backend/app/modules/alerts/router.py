"""
Router do modulo de alertas.

Endpoints para CRUD de regras e consulta de historico.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_roles
from app.modules.alerts.schemas import (
    AlertHistoryResponse,
    AlertRuleCreate,
    AlertRuleResponse,
    AlertRuleUpdate,
)
from app.modules.alerts.service import AlertService
from app.modules.auth.models import User
from app.shared.schemas import MessageResponse

router = APIRouter(
    prefix='/api/alerts',
    tags=['Alerts'],
)


def get_alert_service(db: Session = Depends(get_db)) -> AlertService:
    """Dependency que fornece o servico de alertas."""
    return AlertService(db)


# ------------------------------------------------------------------
# Regras de alerta
# ------------------------------------------------------------------


@router.get('/rules', response_model=list[AlertRuleResponse])
def list_rules(
    include_inactive: bool = Query(False, description='Incluir regras inativas'),
    current_user: User = Depends(require_roles('admin', 'operator')),
    service: AlertService = Depends(get_alert_service),
) -> list[AlertRuleResponse]:
    """
    Lista todas as regras de alerta.

    Requer role admin ou operator.
    """
    return service.get_rules(include_inactive=include_inactive)


@router.get('/rules/{rule_id}', response_model=AlertRuleResponse)
def get_rule(
    rule_id: uuid.UUID,
    current_user: User = Depends(require_roles('admin', 'operator')),
    service: AlertService = Depends(get_alert_service),
) -> AlertRuleResponse:
    """
    Retorna uma regra de alerta pelo ID.

    Requer role admin ou operator.
    """
    return service.get_rule(rule_id)


@router.post('/rules', response_model=AlertRuleResponse, status_code=201)
def create_rule(
    data: AlertRuleCreate,
    current_user: User = Depends(require_roles('admin')),
    service: AlertService = Depends(get_alert_service),
) -> AlertRuleResponse:
    """
    Cria uma nova regra de alerta.

    Tipos disponiveis: failure_rate, duration_exceeded, worker_offline, token_budget.
    Requer role admin.
    """
    return service.create_rule(data.model_dump())


@router.put('/rules/{rule_id}', response_model=AlertRuleResponse)
def update_rule(
    rule_id: uuid.UUID,
    data: AlertRuleUpdate,
    current_user: User = Depends(require_roles('admin')),
    service: AlertService = Depends(get_alert_service),
) -> AlertRuleResponse:
    """
    Atualiza uma regra de alerta existente.

    Requer role admin.
    """
    return service.update_rule(rule_id, data.model_dump(exclude_unset=True))


@router.delete('/rules/{rule_id}', response_model=MessageResponse)
def delete_rule(
    rule_id: uuid.UUID,
    current_user: User = Depends(require_roles('admin')),
    service: AlertService = Depends(get_alert_service),
) -> MessageResponse:
    """
    Exclui (soft delete) uma regra de alerta.

    Requer role admin.
    """
    service.delete_rule(rule_id)
    return MessageResponse(success=True, message='Regra de alerta excluida com sucesso')


# ------------------------------------------------------------------
# Historico de alertas
# ------------------------------------------------------------------


@router.get('/history', response_model=list[AlertHistoryResponse])
def list_history(
    limit: int = Query(50, ge=1, le=200, description='Limite de registros'),
    current_user: User = Depends(require_roles('admin', 'operator', 'viewer')),
    service: AlertService = Depends(get_alert_service),
) -> list[AlertHistoryResponse]:
    """
    Lista o historico de alertas disparados.

    Retorna os alertas mais recentes, ordenados por data decrescente.
    """
    return service.get_history(limit=limit)


@router.get('/count', response_model=dict)
def get_active_alerts_count(
    current_user: User = Depends(require_roles('admin', 'operator', 'viewer')),
    service: AlertService = Depends(get_alert_service),
) -> dict:
    """
    Retorna a contagem de alertas das ultimas 24h.
    """
    return {'count': service.get_active_alerts_count()}


@router.post('/evaluate', response_model=list[dict])
def evaluate_rules(
    current_user: User = Depends(require_roles('admin')),
    service: AlertService = Depends(get_alert_service),
) -> list[dict]:
    """
    Avalia todas as regras ativas manualmente.

    Util para testes. Em producao, a avaliacao e feita pela task periodica.
    Requer role admin.
    """
    return service.evaluate_all_rules()
