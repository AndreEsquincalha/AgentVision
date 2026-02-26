"""
Script para rotacao de chaves Fernet.

Uso:
  ENCRYPTION_KEYS="nova_chave,antiga_chave" python -m scripts.rotate_encryption_keys

IMPORTANTE:
- A primeira chave de ENCRYPTION_KEYS sera usada para criptografar.
- As demais chaves serao usadas apenas para descriptografar.
"""

import sys

from app.database import SessionLocal
from app.modules.delivery.models import DeliveryConfig
from app.modules.projects.models import Project
from app.modules.settings.models import Setting
from app.shared.utils import decrypt_value, encrypt_value


def _reencrypt(value: str) -> str:
    """Descriptografa e recriptografa com a chave atual."""
    decrypted = decrypt_value(value)
    return encrypt_value(decrypted)


def rotate_keys() -> None:
    """Recriptografa todos os valores sensiveis com a chave atual."""
    db = SessionLocal()
    try:
        updated = 0

        settings = db.query(Setting).all()
        for setting in settings:
            if setting.encrypted_value:
                setting.encrypted_value = _reencrypt(setting.encrypted_value)
                updated += 1

        projects = db.query(Project).all()
        for project in projects:
            if project.encrypted_credentials:
                project.encrypted_credentials = _reencrypt(project.encrypted_credentials)
                updated += 1
            if project.encrypted_llm_api_key:
                project.encrypted_llm_api_key = _reencrypt(project.encrypted_llm_api_key)
                updated += 1

        configs = db.query(DeliveryConfig).all()
        for config in configs:
            if config.channel_config:
                config.channel_config = _reencrypt(config.channel_config)
                updated += 1

        db.commit()
        print(f'Rotacao concluida. Registros atualizados: {updated}')
    except Exception as exc:
        db.rollback()
        print(f'Erro na rotacao de chaves: {exc}', file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == '__main__':
    rotate_keys()
