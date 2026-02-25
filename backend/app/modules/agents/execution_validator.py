"""
Validador pre-execucao para agentes de navegacao.

Verifica condicoes necessarias antes de iniciar uma execucao,
evitando gastar recursos (browser, tokens LLM) em execucoes
que estao fadadas a falhar.

Validacoes realizadas:
1. URL base acessivel (HEAD request com timeout de 5s)
2. Credenciais presentes e validas (se configuradas)
3. API key do LLM configurada (exceto para Ollama local)
4. Modelo do LLM especificado

Sprint 10.2.4
"""

import logging
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

# Timeout para verificacao de acessibilidade da URL (segundos)
_URL_CHECK_TIMEOUT: float = 5.0


@dataclass
class ValidationResult:
    """Resultado da validacao pre-execucao."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class ExecutionValidator:
    """
    Validador pre-execucao para evitar gastar recursos
    em execucoes fadadas a falhar.

    Realiza verificacoes rapidas de conectividade, credenciais
    e configuracao do LLM antes de iniciar o agente de navegacao.
    """

    @staticmethod
    def validate(
        base_url: str,
        credentials: dict | None = None,
        llm_config: dict | None = None,
    ) -> ValidationResult:
        """
        Valida condicoes necessarias para execucao.

        Verificacoes:
        1. URL base acessivel (HEAD request, timeout 5s)
        2. Credenciais presentes se configuradas (username/email e password)
        3. API key do LLM valida (formato basico, exceto Ollama)
        4. Modelo do LLM especificado

        Args:
            base_url: URL base do site alvo a ser validada.
            credentials: Dicionario com credenciais de acesso (opcional).
            llm_config: Dicionario com configuracao do LLM (provider, model, api_key).

        Returns:
            ValidationResult com is_valid=True se tudo OK, ou com
            lista de erros e avisos encontrados.
        """
        errors: list[str] = []
        warnings: list[str] = []

        # 1. Verificar acessibilidade da URL
        ExecutionValidator._validate_url(base_url, errors, warnings)

        # 2. Verificar credenciais (se fornecidas)
        if credentials:
            ExecutionValidator._validate_credentials(
                credentials, warnings,
            )

        # 3. Verificar configuracao do LLM
        if llm_config:
            ExecutionValidator._validate_llm_config(
                llm_config, errors, warnings,
            )

        is_valid = len(errors) == 0
        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
        )

    @staticmethod
    def _validate_url(
        base_url: str,
        errors: list[str],
        warnings: list[str],
    ) -> None:
        """
        Verifica se a URL base esta acessivel via HEAD request.

        Erros de conexao e timeout sao considerados erros fatais.
        Status 4xx gera warning (pode requerer login), 5xx gera erro.

        Args:
            base_url: URL a ser verificada.
            errors: Lista de erros para acumular.
            warnings: Lista de avisos para acumular.
        """
        try:
            with httpx.Client(
                timeout=_URL_CHECK_TIMEOUT,
                follow_redirects=True,
            ) as client:
                resp = client.head(base_url)
                if resp.status_code >= 500:
                    errors.append(
                        f'URL {base_url} retornou erro {resp.status_code}'
                    )
                elif resp.status_code >= 400:
                    warnings.append(
                        f'URL {base_url} retornou status '
                        f'{resp.status_code} (pode requerer login)'
                    )
        except httpx.ConnectError:
            errors.append(
                f'URL {base_url} inacessivel (connection error)'
            )
        except httpx.TimeoutException:
            errors.append(
                f'URL {base_url} nao respondeu em '
                f'{int(_URL_CHECK_TIMEOUT)} segundos'
            )
        except Exception as e:
            warnings.append(
                f'Nao foi possivel validar URL {base_url}: {str(e)}'
            )

    @staticmethod
    def _validate_credentials(
        credentials: dict,
        warnings: list[str],
    ) -> None:
        """
        Verifica se as credenciais possuem campos essenciais.

        Nao valida autenticacao real (isso e feito pelo BrowserAgent),
        apenas verifica se os campos username/email e password estao presentes.

        Args:
            credentials: Dicionario com credenciais de acesso.
            warnings: Lista de avisos para acumular.
        """
        username = credentials.get('username') or credentials.get('email', '')
        password = credentials.get('password', '')

        if not username:
            warnings.append(
                'Credenciais configuradas mas sem username/email'
            )
        if not password:
            warnings.append(
                'Credenciais configuradas mas sem password'
            )

    @staticmethod
    def _validate_llm_config(
        llm_config: dict,
        errors: list[str],
        warnings: list[str],
    ) -> None:
        """
        Verifica se a configuracao do LLM esta completa.

        API key e obrigatoria para todos os providers exceto Ollama (local).
        Modelo e recomendado mas nao obrigatorio (gera warning).

        Args:
            llm_config: Dicionario com configuracao do LLM.
            errors: Lista de erros para acumular.
            warnings: Lista de avisos para acumular.
        """
        api_key = llm_config.get('api_key', '')
        provider = llm_config.get('provider', '')
        model = llm_config.get('model', '')

        if not api_key and provider != 'ollama':
            errors.append(
                f'API key do LLM ({provider}) nao configurada'
            )
        if not model:
            warnings.append('Modelo do LLM nao especificado')
