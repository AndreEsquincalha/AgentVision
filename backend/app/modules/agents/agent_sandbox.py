"""
Sandbox de seguranca para agentes de navegacao.

Controla quais dominios o agente pode visitar e quais acoes pode executar,
prevenindo que o agente navegue para sites nao autorizados ou execute acoes
perigosas como downloads, uploads ou execucao de JavaScript arbitrario.

Funcionalidades:
- Allowlist de dominios: restringe navegacao apenas a dominios permitidos
- Blocklist de URLs: bloqueia URLs que correspondem a padroes regex
- Controle de acoes: permite/bloqueia acoes especificas do agente
- Geracao de regras de prompt: regras de sandbox para injetar no prompt do agente
- Registro de violacoes: historico de tentativas bloqueadas

Sprint 10.2.1 / 10.2.2
"""

import logging
import re
from dataclasses import dataclass
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


@dataclass
class SandboxViolation:
    """Violacao de sandbox detectada."""

    violation_type: str  # 'blocked_domain', 'blocked_url', 'blocked_action'
    details: str
    blocked_value: str


class AgentSandbox:
    """
    Sandbox de seguranca para agentes de navegacao.

    Controla quais dominios o agente pode visitar e quais acoes pode executar.
    Registra todas as violacoes para auditoria e logging.
    """

    # Acoes seguras permitidas por padrao
    DEFAULT_ALLOWED_ACTIONS: set[str] = {
        'navigate', 'click', 'type', 'screenshot', 'extract', 'scroll',
        'wait', 'select', 'hover',
    }

    # Acoes perigosas bloqueadas por padrao
    DEFAULT_BLOCKED_ACTIONS: set[str] = {
        'download', 'upload', 'execute_js', 'payment_submit',
    }

    def __init__(
        self,
        allowed_domains: list[str] | None = None,
        blocked_urls: list[str] | None = None,
        allowed_actions: set[str] | None = None,
        blocked_actions: set[str] | None = None,
    ) -> None:
        """
        Inicializa a sandbox com restricoes configuradas.

        Args:
            allowed_domains: Lista de dominios permitidos para navegacao.
                Se fornecida, apenas esses dominios (e seus subdominos)
                podem ser acessados. Se None, qualquer dominio e permitido.
            blocked_urls: Lista de padroes regex para bloquear URLs especificas.
            allowed_actions: Conjunto de acoes permitidas (override do padrao).
            blocked_actions: Conjunto de acoes bloqueadas (override do padrao).
        """
        self._allowed_domains = [
            d.lower().strip() for d in (allowed_domains or [])
        ]
        self._blocked_urls = blocked_urls or []
        self._allowed_actions = allowed_actions or self.DEFAULT_ALLOWED_ACTIONS
        self._blocked_actions = blocked_actions or self.DEFAULT_BLOCKED_ACTIONS
        self._violations: list[SandboxViolation] = []

    def check_url(self, url: str) -> SandboxViolation | None:
        """
        Verifica se uma URL e permitida pela sandbox.

        Primeiro verifica a allowlist de dominios (se configurada),
        depois verifica a blocklist de padroes de URL.

        Args:
            url: URL que o agente deseja visitar.

        Returns:
            SandboxViolation se bloqueada, None se permitida.
        """
        parsed = urlparse(url)
        domain = parsed.hostname or ''
        domain = domain.lower()

        # Se ha allowlist, verificar se o dominio esta nela
        if self._allowed_domains:
            is_allowed = any(
                domain == d or domain.endswith(f'.{d}')
                for d in self._allowed_domains
            )
            if not is_allowed:
                violation = SandboxViolation(
                    violation_type='blocked_domain',
                    details=(
                        f'Dominio "{domain}" nao esta na lista '
                        f'de dominios permitidos'
                    ),
                    blocked_value=url,
                )
                self._violations.append(violation)
                logger.warning('Sandbox: %s', violation.details)
                return violation

        # Verificar blocklist de URLs (padroes regex)
        for blocked_pattern in self._blocked_urls:
            try:
                if re.search(blocked_pattern, url, re.IGNORECASE):
                    violation = SandboxViolation(
                        violation_type='blocked_url',
                        details=(
                            f'URL "{url}" corresponde ao padrao '
                            f'bloqueado "{blocked_pattern}"'
                        ),
                        blocked_value=url,
                    )
                    self._violations.append(violation)
                    logger.warning('Sandbox: %s', violation.details)
                    return violation
            except re.error as e:
                # Padrao regex invalido: logar e pular
                logger.warning(
                    'Sandbox: padrao regex invalido "%s": %s',
                    blocked_pattern, str(e),
                )

        return None

    def check_action(self, action: str) -> SandboxViolation | None:
        """
        Verifica se uma acao e permitida pela sandbox.

        Args:
            action: Nome da acao que o agente deseja executar.

        Returns:
            SandboxViolation se bloqueada, None se permitida.
        """
        action_lower = action.lower()

        if action_lower in self._blocked_actions:
            violation = SandboxViolation(
                violation_type='blocked_action',
                details=f'Acao "{action}" esta bloqueada pela sandbox',
                blocked_value=action,
            )
            self._violations.append(violation)
            logger.warning('Sandbox: %s', violation.details)
            return violation

        return None

    def get_prompt_rules(self) -> str:
        """
        Gera regras de sandbox para incluir no prompt do agente.

        As regras sao formatadas como uma lista de instrucoes claras
        que o agente LLM deve seguir durante a navegacao.

        Returns:
            String com regras formatadas, uma por linha, prefixadas com "- ".
        """
        rules: list[str] = []

        if self._allowed_domains:
            domains_str = ', '.join(self._allowed_domains)
            rules.append(
                f'APENAS navegue em dominios permitidos: {domains_str}'
            )
            rules.append('NAO acesse URLs fora desses dominios')

        if self._blocked_actions:
            actions_str = ', '.join(sorted(self._blocked_actions))
            rules.append(f'ACOES PROIBIDAS: {actions_str}')

        rules.append('NAO faca downloads de arquivos')
        rules.append('NAO execute JavaScript arbitrario')
        rules.append('NAO preencha formularios de pagamento')

        return '\n'.join(f'- {r}' for r in rules)

    @property
    def violations(self) -> list[SandboxViolation]:
        """Retorna copia da lista de violacoes registradas."""
        return self._violations.copy()

    @property
    def violation_count(self) -> int:
        """Retorna o numero total de violacoes registradas."""
        return len(self._violations)

    @property
    def has_violations(self) -> bool:
        """Indica se houve alguma violacao de sandbox."""
        return len(self._violations) > 0
