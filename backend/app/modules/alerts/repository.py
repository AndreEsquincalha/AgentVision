"""
Repositorio de acesso a dados do modulo de alertas.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.alerts.models import AlertHistory, AlertRule
from app.shared.utils import utc_now


class AlertRuleRepository:
    """Repositorio para regras de alerta (com soft delete)."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_all(self, include_inactive: bool = False) -> list[AlertRule]:
        """Retorna todas as regras nao excluidas."""
        stmt = select(AlertRule).where(AlertRule.deleted_at.is_(None))
        if not include_inactive:
            stmt = stmt.where(AlertRule.is_active.is_(True))
        stmt = stmt.order_by(AlertRule.created_at.desc())
        return list(self._db.execute(stmt).scalars().all())

    def get_by_id(self, rule_id: uuid.UUID) -> AlertRule | None:
        """Busca regra por ID (nao excluida)."""
        stmt = select(AlertRule).where(
            AlertRule.id == rule_id,
            AlertRule.deleted_at.is_(None),
        )
        return self._db.execute(stmt).scalar_one_or_none()

    def create(self, data: dict) -> AlertRule:
        """Cria nova regra de alerta."""
        rule = AlertRule(**data)
        self._db.add(rule)
        self._db.commit()
        self._db.refresh(rule)
        return rule

    def update(self, rule_id: uuid.UUID, data: dict) -> AlertRule | None:
        """Atualiza uma regra existente."""
        rule = self.get_by_id(rule_id)
        if not rule:
            return None
        for key, value in data.items():
            if value is not None:
                setattr(rule, key, value)
        self._db.commit()
        self._db.refresh(rule)
        return rule

    def delete(self, rule_id: uuid.UUID) -> bool:
        """Soft delete de uma regra."""
        rule = self.get_by_id(rule_id)
        if not rule:
            return False
        rule.deleted_at = utc_now()
        self._db.commit()
        return True


class AlertHistoryRepository:
    """Repositorio para historico de alertas."""

    def __init__(self, db: Session) -> None:
        self._db = db

    def get_recent(self, limit: int = 50) -> list[AlertHistory]:
        """Retorna os alertas mais recentes."""
        stmt = select(AlertHistory).order_by(
            AlertHistory.created_at.desc(),
        ).limit(limit)
        return list(self._db.execute(stmt).scalars().all())

    def get_by_rule_id(
        self,
        rule_id: uuid.UUID,
        limit: int = 20,
    ) -> list[AlertHistory]:
        """Retorna historico de alertas de uma regra."""
        stmt = select(AlertHistory).where(
            AlertHistory.rule_id == rule_id,
        ).order_by(
            AlertHistory.created_at.desc(),
        ).limit(limit)
        return list(self._db.execute(stmt).scalars().all())

    def create(self, data: dict) -> AlertHistory:
        """Registra um alerta disparado."""
        alert = AlertHistory(**data)
        self._db.add(alert)
        self._db.commit()
        self._db.refresh(alert)
        return alert

    def count_recent(self, hours: int = 24) -> int:
        """Conta alertas das ultimas N horas."""
        from datetime import timedelta
        cutoff = utc_now() - timedelta(hours=hours)
        stmt = select(func.count(AlertHistory.id)).where(
            AlertHistory.created_at >= cutoff,
        )
        return self._db.execute(stmt).scalar_one()
