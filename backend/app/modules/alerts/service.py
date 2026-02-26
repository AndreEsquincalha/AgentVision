"""
Servico de alertas do AgentVision.

Contem a engine de avaliacao de regras e logica de notificacao.
"""

import json
import logging
import uuid
from datetime import timedelta

import requests
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.alerts.models import AlertHistory, AlertRule
from app.modules.alerts.repository import AlertHistoryRepository, AlertRuleRepository
from app.modules.alerts.schemas import AlertHistoryResponse, AlertRuleResponse
from app.modules.executions.models import Execution
from app.shared.utils import utc_now

logger = logging.getLogger(__name__)

# Chave Redis para cooldown de alertas
_COOLDOWN_KEY_PREFIX = 'alert_cooldown:'


class AlertService:
    """
    Servico de alertas com engine de avaliacao de regras.

    Avalia regras configuradas, verifica cooldown via Redis,
    e dispara notificacoes via email ou webhook.
    """

    def __init__(self, db: Session) -> None:
        self._db = db
        self._rule_repo = AlertRuleRepository(db)
        self._history_repo = AlertHistoryRepository(db)

    # ------------------------------------------------------------------
    # CRUD de regras
    # ------------------------------------------------------------------

    def get_rules(self, include_inactive: bool = False) -> list[AlertRuleResponse]:
        """Retorna todas as regras de alerta."""
        rules = self._rule_repo.get_all(include_inactive=include_inactive)
        return [AlertRuleResponse.model_validate(r) for r in rules]

    def get_rule(self, rule_id: uuid.UUID) -> AlertRuleResponse:
        """Retorna uma regra pelo ID."""
        from app.shared.exceptions import NotFoundException
        rule = self._rule_repo.get_by_id(rule_id)
        if not rule:
            raise NotFoundException('Regra de alerta nao encontrada')
        return AlertRuleResponse.model_validate(rule)

    def create_rule(self, data: dict) -> AlertRuleResponse:
        """Cria uma nova regra de alerta."""
        rule = self._rule_repo.create(data)
        return AlertRuleResponse.model_validate(rule)

    def update_rule(self, rule_id: uuid.UUID, data: dict) -> AlertRuleResponse:
        """Atualiza uma regra existente."""
        from app.shared.exceptions import NotFoundException
        rule = self._rule_repo.update(rule_id, data)
        if not rule:
            raise NotFoundException('Regra de alerta nao encontrada')
        return AlertRuleResponse.model_validate(rule)

    def delete_rule(self, rule_id: uuid.UUID) -> bool:
        """Exclui (soft delete) uma regra."""
        from app.shared.exceptions import NotFoundException
        if not self._rule_repo.delete(rule_id):
            raise NotFoundException('Regra de alerta nao encontrada')
        return True

    # ------------------------------------------------------------------
    # Historico
    # ------------------------------------------------------------------

    def get_history(self, limit: int = 50) -> list[AlertHistoryResponse]:
        """Retorna historico de alertas disparados."""
        alerts = self._history_repo.get_recent(limit=limit)
        return [AlertHistoryResponse.model_validate(a) for a in alerts]

    def get_active_alerts_count(self) -> int:
        """Retorna contagem de alertas das ultimas 24h."""
        return self._history_repo.count_recent(hours=24)

    # ------------------------------------------------------------------
    # Engine de avaliacao
    # ------------------------------------------------------------------

    def evaluate_all_rules(self) -> list[dict]:
        """
        Avalia todas as regras ativas.

        Verifica cooldown, avalia condicao, dispara notificacao e registra historico.
        Retorna lista de alertas disparados.
        """
        rules = self._rule_repo.get_all(include_inactive=False)
        fired: list[dict] = []

        for rule in rules:
            try:
                if self._is_in_cooldown(rule):
                    continue

                result = self._evaluate_rule(rule)
                if result is None:
                    continue

                # Registrar alerta
                message, details = result
                notified, notify_error = self._send_notification(rule, message, details)
                self._set_cooldown(rule)

                history = self._history_repo.create({
                    'rule_id': rule.id,
                    'rule_name': rule.name,
                    'rule_type': rule.rule_type,
                    'severity': rule.severity,
                    'message': message,
                    'details': details,
                    'notified': notified,
                    'notify_channel': rule.notify_channel,
                    'notify_error': notify_error,
                })

                fired.append({
                    'rule': rule.name,
                    'message': message,
                    'severity': rule.severity,
                    'notified': notified,
                })

                logger.info(
                    'Alerta disparado: rule=%s type=%s severity=%s notified=%s',
                    rule.name,
                    rule.rule_type,
                    rule.severity,
                    notified,
                )

            except Exception as e:
                logger.error(
                    'Erro ao avaliar regra %s: %s',
                    rule.name,
                    str(e),
                )

        return fired

    def _evaluate_rule(self, rule: AlertRule) -> tuple[str, dict] | None:
        """
        Avalia uma regra individual.

        Retorna (message, details) se a regra disparou, ou None.
        """
        evaluators = {
            'failure_rate': self._evaluate_failure_rate,
            'duration_exceeded': self._evaluate_duration_exceeded,
            'worker_offline': self._evaluate_worker_offline,
            'token_budget': self._evaluate_token_budget,
        }

        evaluator = evaluators.get(rule.rule_type)
        if not evaluator:
            logger.warning('Tipo de regra desconhecido: %s', rule.rule_type)
            return None

        return evaluator(rule.conditions)

    def _evaluate_failure_rate(self, conditions: dict) -> tuple[str, dict] | None:
        """
        Avalia taxa de falha.

        Condicoes: threshold_pct (int), last_n_executions (int), job_id (str|null)
        """
        threshold_pct = conditions.get('threshold_pct', 50)
        last_n = conditions.get('last_n_executions', 10)
        job_id = conditions.get('job_id')

        stmt = select(Execution.status)
        if job_id:
            stmt = stmt.where(Execution.job_id == uuid.UUID(job_id))
        stmt = stmt.order_by(Execution.created_at.desc()).limit(last_n)

        rows = self._db.execute(stmt).scalars().all()
        if len(rows) < 2:
            return None

        failed_count = sum(1 for s in rows if s == 'failed')
        failure_rate = (failed_count / len(rows)) * 100

        if failure_rate >= threshold_pct:
            return (
                f'Taxa de falha em {failure_rate:.0f}% '
                f'({failed_count}/{len(rows)} execucoes)',
                {
                    'failure_rate_pct': round(failure_rate, 1),
                    'failed_count': failed_count,
                    'total_evaluated': len(rows),
                    'threshold_pct': threshold_pct,
                    'job_id': job_id,
                },
            )
        return None

    def _evaluate_duration_exceeded(self, conditions: dict) -> tuple[str, dict] | None:
        """
        Avalia execucoes com duracao excessiva.

        Condicoes: max_minutes (int), job_id (str|null)
        """
        max_minutes = conditions.get('max_minutes', 30)
        job_id = conditions.get('job_id')

        stmt = select(Execution).where(
            Execution.status == 'running',
            Execution.started_at.isnot(None),
        )
        if job_id:
            stmt = stmt.where(Execution.job_id == uuid.UUID(job_id))

        running = list(self._db.execute(stmt).scalars().all())
        now = utc_now()
        exceeded: list[dict] = []

        for ex in running:
            if ex.started_at:
                elapsed = (now - ex.started_at).total_seconds() / 60
                if elapsed > max_minutes:
                    exceeded.append({
                        'execution_id': str(ex.id),
                        'job_id': str(ex.job_id),
                        'elapsed_minutes': round(elapsed, 1),
                    })

        if exceeded:
            return (
                f'{len(exceeded)} execucao(oes) com duracao > {max_minutes} minutos',
                {
                    'max_minutes': max_minutes,
                    'exceeded_executions': exceeded,
                },
            )
        return None

    def _evaluate_worker_offline(self, conditions: dict) -> tuple[str, dict] | None:
        """
        Avalia se workers Celery estao offline.
        """
        try:
            from app.celery_app import celery_app as _celery

            inspector = _celery.control.inspect(timeout=3.0)
            ping_result = inspector.ping() or {}
            worker_count = len(ping_result)

            if worker_count == 0:
                return (
                    'Nenhum worker Celery online detectado',
                    {'workers_online': 0},
                )
        except Exception as e:
            return (
                f'Nao foi possivel verificar workers Celery: {str(e)[:100]}',
                {'error': str(e)[:200]},
            )

        return None

    def _evaluate_token_budget(self, conditions: dict) -> tuple[str, dict] | None:
        """
        Avalia se o budget de tokens foi excedido.

        Condicoes: max_tokens_per_day (int), max_cost_per_day_usd (float)
        """
        from app.modules.agents.token_tracker import TokenTracker

        max_tokens = conditions.get('max_tokens_per_day', 0)
        max_cost = conditions.get('max_cost_per_day_usd', 0.0)

        now = utc_now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        total_tokens = TokenTracker.get_total_tokens_for_period(
            date_from=today_start,
            date_to=now,
        )

        usage_data = TokenTracker.get_usage_for_period(
            date_from=today_start,
            date_to=now,
        )
        total_cost = sum(row.get('estimated_cost_usd', 0.0) for row in usage_data)

        exceeded_reasons: list[str] = []
        details: dict = {
            'total_tokens_today': total_tokens,
            'total_cost_today_usd': round(total_cost, 4),
        }

        if max_tokens > 0 and total_tokens > max_tokens:
            exceeded_reasons.append(
                f'tokens ({total_tokens:,} > {max_tokens:,})'
            )
            details['max_tokens_per_day'] = max_tokens

        if max_cost > 0 and total_cost > max_cost:
            exceeded_reasons.append(
                f'custo (${total_cost:.4f} > ${max_cost:.4f})'
            )
            details['max_cost_per_day_usd'] = max_cost

        if exceeded_reasons:
            return (
                f'Budget excedido: {", ".join(exceeded_reasons)}',
                details,
            )
        return None

    # ------------------------------------------------------------------
    # Cooldown (Redis)
    # ------------------------------------------------------------------

    def _is_in_cooldown(self, rule: AlertRule) -> bool:
        """Verifica se a regra esta em cooldown."""
        try:
            from app.shared.redis_client import get_redis_client
            redis = get_redis_client()
            key = f'{_COOLDOWN_KEY_PREFIX}{rule.id}'
            return redis.exists(key) > 0
        except Exception:
            return False

    def _set_cooldown(self, rule: AlertRule) -> None:
        """Define cooldown para uma regra no Redis."""
        try:
            from app.shared.redis_client import get_redis_client
            redis = get_redis_client()
            key = f'{_COOLDOWN_KEY_PREFIX}{rule.id}'
            ttl_seconds = rule.cooldown_minutes * 60
            redis.set(key, '1', ex=ttl_seconds)
        except Exception as e:
            logger.warning('Falha ao definir cooldown para regra %s: %s', rule.name, e)

    # ------------------------------------------------------------------
    # Notificacao
    # ------------------------------------------------------------------

    def _send_notification(
        self,
        rule: AlertRule,
        message: str,
        details: dict,
    ) -> tuple[bool, str | None]:
        """
        Envia notificacao via canal configurado.

        Retorna (success, error_message).
        """
        if rule.notify_channel == 'email':
            return self._send_email_notification(rule, message, details)
        elif rule.notify_channel == 'webhook':
            return self._send_webhook_notification(rule, message, details)
        else:
            return False, f'Canal desconhecido: {rule.notify_channel}'

    def _send_email_notification(
        self,
        rule: AlertRule,
        message: str,
        details: dict,
    ) -> tuple[bool, str | None]:
        """Envia alerta via email usando configuracoes SMTP do sistema."""
        try:
            from app.modules.settings.repository import SettingRepository
            from app.modules.settings.service import SettingService

            setting_service = SettingService(SettingRepository(self._db))
            smtp_settings = setting_service.get_settings('smtp')
            smtp = smtp_settings.settings

            if not smtp.get('host'):
                return False, 'SMTP nao configurado'

            import smtplib
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText

            severity_colors = {
                'info': '#22D3EE',
                'warning': '#F59E0B',
                'critical': '#EF4444',
            }
            color = severity_colors.get(rule.severity, '#6B7280')

            html = f"""
            <div style="background:#0F1117;padding:24px;font-family:Inter,sans-serif;">
              <div style="max-width:600px;margin:0 auto;background:#1A1D2E;border-radius:12px;
                          border:1px solid #2E3348;overflow:hidden;">
                <div style="background:{color};padding:16px 24px;">
                  <h2 style="margin:0;color:#fff;font-size:18px;">
                    AgentVision Alerta [{rule.severity.upper()}]
                  </h2>
                </div>
                <div style="padding:24px;">
                  <p style="color:#F9FAFB;font-size:15px;margin:0 0 12px;">
                    <strong>{rule.name}</strong>
                  </p>
                  <p style="color:#9CA3AF;font-size:14px;margin:0 0 16px;">{message}</p>
                  <pre style="background:#242838;padding:12px;border-radius:8px;color:#9CA3AF;
                              font-size:12px;overflow:auto;font-family:JetBrains Mono,monospace;">
{json.dumps(details, indent=2, ensure_ascii=False)}</pre>
                  <p style="color:#6B7280;font-size:11px;margin:16px 0 0;">
                    Tipo: {rule.rule_type} | Cooldown: {rule.cooldown_minutes}min
                  </p>
                </div>
              </div>
            </div>
            """

            msg = MIMEMultipart('alternative')
            msg['Subject'] = f'[AgentVision {rule.severity.upper()}] {rule.name}'
            msg['From'] = smtp.get('sender_email', 'noreply@agentvision.local')
            msg['To'] = ', '.join(rule.notify_recipients)
            msg.attach(MIMEText(f'{rule.name}: {message}', 'plain'))
            msg.attach(MIMEText(html, 'html'))

            port = int(smtp.get('port', 587))
            use_tls = smtp.get('use_tls', 'true').lower() == 'true'

            with smtplib.SMTP(smtp['host'], port, timeout=15) as server:
                if use_tls:
                    server.starttls()
                username = smtp.get('username', '')
                password = smtp.get('password', '')
                if username and password:
                    server.login(username, password)
                server.sendmail(
                    msg['From'],
                    rule.notify_recipients,
                    msg.as_string(),
                )

            return True, None

        except Exception as e:
            logger.error('Falha ao enviar email de alerta: %s', e)
            return False, str(e)[:300]

    def _send_webhook_notification(
        self,
        rule: AlertRule,
        message: str,
        details: dict,
    ) -> tuple[bool, str | None]:
        """Envia alerta via webhook (POST JSON)."""
        try:
            payload = {
                'alert': {
                    'rule_name': rule.name,
                    'rule_type': rule.rule_type,
                    'severity': rule.severity,
                    'message': message,
                    'details': details,
                    'timestamp': utc_now().isoformat(),
                },
                'source': 'AgentVision',
            }

            for url in rule.notify_recipients:
                response = requests.post(
                    url,
                    json=payload,
                    timeout=10,
                    headers={'Content-Type': 'application/json'},
                )
                if response.status_code >= 400:
                    return False, f'Webhook retornou {response.status_code}: {response.text[:200]}'

            return True, None

        except Exception as e:
            logger.error('Falha ao enviar webhook de alerta: %s', e)
            return False, str(e)[:300]
