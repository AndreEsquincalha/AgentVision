from datetime import UTC, datetime

from app.celery_app import celery_app
from app.database import SessionLocal
from app.modules.auth.repository import TokenBlacklistRepository


@celery_app.task(name='app.modules.auth.tasks.cleanup_token_blacklist')
def cleanup_token_blacklist() -> int:
    """
    Remove tokens expirados da blacklist.
    """
    db = SessionLocal()
    try:
        repo = TokenBlacklistRepository(db)
        now = datetime.now(UTC)
        return repo.cleanup_expired(now)
    finally:
        db.close()
