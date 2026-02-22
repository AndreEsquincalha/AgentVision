from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool

from alembic import context

from app.config import settings
from app.database import Base

# Importar todos os modelos para que o Alembic detecte as tabelas.
# Adicione os imports de novos modelos conforme forem criados.
from app.modules.auth.models import User  # noqa: F401
from app.modules.projects.models import Project  # noqa: F401
from app.modules.jobs.models import Job  # noqa: F401
from app.modules.executions.models import Execution  # noqa: F401
from app.modules.delivery.models import DeliveryConfig, DeliveryLog  # noqa: F401
# from app.modules.prompts.models import PromptTemplate
# from app.modules.settings.models import Setting

# Configuracao do Alembic
config = context.config

# Configura logging a partir do arquivo alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Sobrescreve a URL do banco com a configuracao da aplicacao
config.set_main_option('sqlalchemy.url', settings.database_url)

# Metadata dos modelos para autogenerate
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """
    Executa migracoes em modo 'offline'.

    Gera SQL sem precisar de conexao com o banco.
    """
    url = config.get_main_option('sqlalchemy.url')
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={'paramstyle': 'named'},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Executa migracoes em modo 'online'.

    Cria uma conexao com o banco e aplica as migracoes.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
