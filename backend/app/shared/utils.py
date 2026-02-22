import uuid
from datetime import UTC, datetime

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


def get_fernet() -> Fernet:
    """Retorna uma instancia do Fernet com a chave de criptografia configurada."""
    return Fernet(settings.encryption_key.encode())


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


def generate_uuid() -> uuid.UUID:
    """Gera um novo UUID v4."""
    return uuid.uuid4()


def utc_now() -> datetime:
    """Retorna a data e hora atual em UTC."""
    return datetime.now(UTC)
