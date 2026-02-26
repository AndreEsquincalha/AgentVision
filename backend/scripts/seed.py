"""
Script de seed para criacao do usuario admin padrao.

Executar via: python -m scripts.seed
"""

import sys

from app.config import settings
from app.database import SessionLocal
from app.modules.auth.models import User
from app.modules.auth.repository import UserRepository
from app.modules.auth.service import hash_password
from app.modules.auth.models import UserRole


def seed_admin_user() -> None:
    """
    Cria o usuario admin padrao se ele ainda nao existir.

    Utiliza as configuracoes de ADMIN_EMAIL, ADMIN_PASSWORD e ADMIN_NAME
    definidas nas variaveis de ambiente.
    """
    db = SessionLocal()
    try:
        repository = UserRepository(db)

        # Verifica se o usuario admin ja existe
        existing_user = repository.get_by_email(settings.admin_email)
        if existing_user:
            print(
                f'Usuario admin ja existe: {settings.admin_email}. '
                f'Seed ignorado.'
            )
            return

        # Cria o usuario admin
        hashed_pwd = hash_password(settings.admin_password)
        user_data = {
            'email': settings.admin_email,
            'hashed_password': hashed_pwd,
            'name': settings.admin_name,
            'is_active': True,
            'role': UserRole.admin.value,
        }

        user = repository.create(user_data)
        print(
            f'Usuario admin criado com sucesso!\n'
            f'  Email: {user.email}\n'
            f'  Nome: {user.name}\n'
            f'  ID: {user.id}'
        )
    except Exception as e:
        print(f'Erro ao criar usuario admin: {e}', file=sys.stderr)
        sys.exit(1)
    finally:
        db.close()


if __name__ == '__main__':
    seed_admin_user()
