from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import settings

# Cria engine de conexao com o PostgreSQL
engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=False,
)

# Fabrica de sessoes
SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """Classe base declarativa para todos os modelos SQLAlchemy."""
    pass


def get_db() -> Generator[Session, None, None]:
    """Dependency do FastAPI que fornece uma sessao do banco de dados."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
