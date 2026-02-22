from collections.abc import Generator

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.shared.storage import StorageClient


def get_storage_client() -> StorageClient:
    """Dependency que fornece o cliente de storage (MinIO/S3)."""
    return StorageClient()


# Nota: get_current_user sera implementado no modulo auth (Sprint 2).
# Sera adicionado aqui apos a implementacao do modulo de autenticacao JWT.
