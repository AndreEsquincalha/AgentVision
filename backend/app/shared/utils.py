import json
import uuid
from datetime import UTC, datetime

from cryptography.fernet import Fernet, InvalidToken, MultiFernet

from app.config import settings


def _get_fernet_keys() -> list[bytes]:
    """
    Retorna a lista de chaves Fernet configuradas.

    Suporta rotacao de chaves via ENCRYPTION_KEYS (lista separada por virgula).
    A primeira chave e usada para criptografar; todas sao usadas para descriptografar.
    """
    keys: list[bytes] = []
    raw_keys = getattr(settings, 'encryption_keys', None)
    if raw_keys:
        for raw_key in raw_keys.split(','):
            cleaned = raw_key.strip()
            if cleaned:
                keys.append(cleaned.encode('utf-8'))
    if not keys:
        keys.append(settings.encryption_key.encode('utf-8'))
    return keys


def get_fernet() -> MultiFernet:
    """Retorna uma instancia MultiFernet com todas as chaves configuradas."""
    keys = _get_fernet_keys()
    fernets = [Fernet(key) for key in keys]
    return MultiFernet(fernets)


def encrypt_value(value: str) -> str:
    """
    Criptografa um valor usando Fernet.

    Args:
        value: Valor em texto puro para criptografar.

    Returns:
        Valor criptografado em formato string (base64).
    """
    fernet = get_fernet()
    encrypted: bytes = fernet.encrypt(value.encode('utf-8'))
    return encrypted.decode('utf-8')


def decrypt_value(encrypted_value: str) -> str:
    """
    Descriptografa um valor criptografado com Fernet.

    Args:
        encrypted_value: Valor criptografado em formato string (base64).

    Returns:
        Valor original em texto puro.

    Raises:
        InvalidToken: Se o valor nao puder ser descriptografado.
    """
    fernet = get_fernet()
    decrypted: bytes = fernet.decrypt(encrypted_value.encode('utf-8'))
    return decrypted.decode('utf-8')


def encrypt_dict(value: dict) -> str:
    """
    Criptografa um dicionario como JSON.
    """
    payload = json.dumps(value, ensure_ascii=True)
    return encrypt_value(payload)


def decrypt_dict(encrypted_value: str) -> dict:
    """
    Descriptografa um JSON criptografado e retorna dict.
    """
    decrypted = decrypt_value(encrypted_value)
    return json.loads(decrypted)


def generate_uuid() -> uuid.UUID:
    """Gera um novo UUID v4."""
    return uuid.uuid4()


def utc_now() -> datetime:
    """Retorna a data e hora atual em UTC."""
    return datetime.now(UTC)
