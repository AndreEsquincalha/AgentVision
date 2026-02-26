import json
import re
from typing import Any

# Regex para remover caracteres de controle ASCII
_CONTROL_CHARS_RE = re.compile(r'[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]')

# Regex para caracteres potencialmente perigosos em nomes
_DANGEROUS_NAME_CHARS_RE = re.compile(r'[<>"\'`\\]')

# Chaves sensiveis para mascaramento
_SENSITIVE_KEYS = (
    'password',
    'passwd',
    'secret',
    'token',
    'api_key',
    'access_key',
    'private_key',
)

_COMMON_PASSWORDS: set[str] | None = None


def _load_common_passwords() -> set[str]:
    """
    Carrega uma lista de senhas comuns.

    Usa uma lista interna combinada com sequencias numericas
    para cobrir um conjunto amplo de senhas frequentes.
    """
    common: set[str] = {
        'password', 'password1', 'password123', '123456', '123456789',
        '12345678', '1234567', '1234567890', '111111', '000000',
        'qwerty', 'qwerty123', 'abc123', 'iloveyou', 'letmein',
        'welcome', 'admin', 'admin123', 'login', 'senha',
        'qwertyuiop', '123123', '654321', '1q2w3e4r',
        '1234', '12345', '1234567', '12345678', '123456789',
        'monkey', 'dragon', 'football', 'baseball', 'master',
        'shadow', 'sunshine', 'princess', 'trustno1', 'access',
        'superman', 'batman', 'hello', 'freedom', 'whatever',
        'qazwsx', 'qazwsx123', 'passw0rd', 'password!', 'senha123',
    }

    # Adiciona sequencias numericas comuns (000000 a 000999)
    for i in range(1000):
        common.add(f'{i:06d}')

    return common


def get_common_passwords() -> set[str]:
    """Retorna a lista de senhas comuns (cacheada)."""
    global _COMMON_PASSWORDS
    if _COMMON_PASSWORDS is None:
        _COMMON_PASSWORDS = _load_common_passwords()
    return _COMMON_PASSWORDS


def sanitize_text(value: str) -> str:
    """
    Sanitiza um texto removendo caracteres de controle e trim.
    """
    if value is None:
        return value
    cleaned = _CONTROL_CHARS_RE.sub('', value)
    return cleaned.strip()


def sanitize_name(value: str) -> str:
    """
    Sanitiza nomes removendo caracteres perigosos e trim.
    """
    cleaned = sanitize_text(value)
    cleaned = _DANGEROUS_NAME_CHARS_RE.sub('', cleaned)
    return re.sub(r'\s+', ' ', cleaned).strip()


def sanitize_email_recipient(value: str) -> str:
    """
    Sanitiza destinatarios removendo CR/LF e trim.
    """
    if value is None:
        return value
    cleaned = value.replace('\r', '').replace('\n', '').strip()
    return sanitize_text(cleaned)


def sanitize_string_list(values: list[str] | None) -> list[str] | None:
    """Sanitiza uma lista de strings."""
    if values is None:
        return None
    return [sanitize_text(v) for v in values if v is not None]


def sanitize_string_dict(data: dict | None) -> dict | None:
    """Sanitiza valores string dentro de um dict (recursivo)."""
    if data is None:
        return None
    cleaned: dict = {}
    for key, value in data.items():
        if isinstance(value, str):
            cleaned[key] = sanitize_text(value)
        elif isinstance(value, dict):
            cleaned[key] = sanitize_string_dict(value)
        elif isinstance(value, list):
            cleaned_list = []
            for item in value:
                if isinstance(item, str):
                    cleaned_list.append(sanitize_text(item))
                elif isinstance(item, dict):
                    cleaned_list.append(sanitize_string_dict(item))
                else:
                    cleaned_list.append(item)
            cleaned[key] = cleaned_list
        else:
            cleaned[key] = value
    return cleaned


def mask_sensitive_dict(data: dict | None) -> dict | None:
    """Mascara chaves sensiveis em um dicionario."""
    if data is None:
        return None
    masked: dict = {}
    for key, value in data.items():
        if any(s in key.lower() for s in _SENSITIVE_KEYS):
            masked[key] = '****'
        elif isinstance(value, dict):
            masked[key] = mask_sensitive_dict(value)
        elif isinstance(value, list):
            cleaned_list = []
            for item in value:
                if isinstance(item, dict):
                    cleaned_list.append(mask_sensitive_dict(item))
                else:
                    cleaned_list.append(item)
            masked[key] = cleaned_list
        else:
            masked[key] = value
    return masked


def validate_json_size(value: Any, max_bytes: int, field_name: str) -> Any:
    """
    Valida tamanho maximo de um campo JSON.
    """
    if value is None:
        return value
    try:
        payload = json.dumps(value, ensure_ascii=True)
    except (TypeError, ValueError):
        raise ValueError(f'Campo {field_name} possui JSON invalido')
    if len(payload.encode('utf-8')) > max_bytes:
        raise ValueError(
            f'Campo {field_name} excede o limite de {max_bytes // 1024}KB'
        )
    return value


def validate_password_strength(password: str) -> str:
    """
    Valida requisitos de senha forte.
    """
    if len(password) < 12:
        raise ValueError('A senha deve ter pelo menos 12 caracteres')
    if not re.search(r'[A-Z]', password):
        raise ValueError('A senha deve conter pelo menos 1 letra maiuscula')
    if not re.search(r'[a-z]', password):
        raise ValueError('A senha deve conter pelo menos 1 letra minuscula')
    if not re.search(r'\d', password):
        raise ValueError('A senha deve conter pelo menos 1 numero')
    if not re.search(r'[^A-Za-z0-9]', password):
        raise ValueError('A senha deve conter pelo menos 1 caractere especial')

    lowered = password.lower()
    if lowered in get_common_passwords():
        raise ValueError('A senha informada e muito comum')

    return password
