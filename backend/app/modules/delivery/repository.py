import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modules.delivery.models import DeliveryConfig, DeliveryLog
from app.shared.utils import utc_now


class DeliveryRepository:
    """
    Repositorio de acesso a dados de configuracoes e logs de entrega.

    Responsavel por operacoes de leitura e escrita nas tabelas
    delivery_configs e delivery_logs.
    Nao contem logica de negocio — apenas acesso a dados.
    """

    def __init__(self, db: Session) -> None:
        """Inicializa o repositorio com a sessao do banco."""
        self._db = db

    # -------------------------------------------------------------------------
    # DeliveryConfig
    # -------------------------------------------------------------------------

    def get_configs_by_job(self, job_id: uuid.UUID) -> list[DeliveryConfig]:
        """
        Busca todas as configuracoes de entrega de um job.

        Args:
            job_id: ID (UUID) do job.

        Returns:
            Lista de configuracoes de entrega do job.
        """
        stmt = select(DeliveryConfig).where(
            DeliveryConfig.job_id == job_id,
            DeliveryConfig.deleted_at.is_(None),
        ).order_by(DeliveryConfig.created_at.desc())

        return list(self._db.execute(stmt).scalars().all())

    def get_active_configs_by_job(self, job_id: uuid.UUID) -> list[DeliveryConfig]:
        """
        Busca configuracoes de entrega ativas de um job.

        Args:
            job_id: ID (UUID) do job.

        Returns:
            Lista de configuracoes de entrega ativas do job.
        """
        stmt = select(DeliveryConfig).where(
            DeliveryConfig.job_id == job_id,
            DeliveryConfig.deleted_at.is_(None),
            DeliveryConfig.is_active.is_(True),
        ).order_by(DeliveryConfig.created_at.desc())

        return list(self._db.execute(stmt).scalars().all())

    def get_config_by_id(self, config_id: uuid.UUID) -> DeliveryConfig | None:
        """
        Busca uma configuracao de entrega pelo ID.

        Args:
            config_id: ID (UUID) da configuracao.

        Returns:
            DeliveryConfig encontrada ou None.
        """
        stmt = select(DeliveryConfig).where(
            DeliveryConfig.id == config_id,
            DeliveryConfig.deleted_at.is_(None),
        )
        return self._db.execute(stmt).scalar_one_or_none()

    def create_config(self, config_data: dict) -> DeliveryConfig:
        """
        Cria uma nova configuracao de entrega.

        Args:
            config_data: Dicionario com os dados da configuracao.

        Returns:
            DeliveryConfig criada.
        """
        config = DeliveryConfig(**config_data)
        self._db.add(config)
        self._db.commit()
        self._db.refresh(config)
        return config

    def update_config(
        self,
        config_id: uuid.UUID,
        config_data: dict,
    ) -> DeliveryConfig | None:
        """
        Atualiza uma configuracao de entrega existente.

        Args:
            config_id: ID (UUID) da configuracao a ser atualizada.
            config_data: Dicionario com os campos a atualizar.

        Returns:
            DeliveryConfig atualizada ou None se nao encontrada.
        """
        config = self.get_config_by_id(config_id)
        if not config:
            return None

        for key, value in config_data.items():
            setattr(config, key, value)

        self._db.commit()
        self._db.refresh(config)
        return config

    def delete_config(self, config_id: uuid.UUID) -> bool:
        """
        Realiza soft delete de uma configuracao de entrega.

        Args:
            config_id: ID (UUID) da configuracao a ser excluida.

        Returns:
            True se excluida, False se nao encontrada.
        """
        config = self.get_config_by_id(config_id)
        if not config:
            return False

        config.deleted_at = utc_now()
        config.is_active = False
        self._db.commit()
        return True

    # -------------------------------------------------------------------------
    # DeliveryLog
    # -------------------------------------------------------------------------

    def create_log(self, log_data: dict) -> DeliveryLog:
        """
        Cria um novo registro de log de entrega.

        Args:
            log_data: Dicionario com os dados do log.

        Returns:
            DeliveryLog criado.
        """
        log = DeliveryLog(**log_data)
        self._db.add(log)
        self._db.commit()
        self._db.refresh(log)
        return log

    def update_log(
        self,
        log_id: uuid.UUID,
        log_data: dict,
    ) -> DeliveryLog | None:
        """
        Atualiza um registro de log de entrega.

        Args:
            log_id: ID (UUID) do log a ser atualizado.
            log_data: Dicionario com os campos a atualizar.

        Returns:
            DeliveryLog atualizado ou None se nao encontrado.
        """
        stmt = select(DeliveryLog).where(DeliveryLog.id == log_id)
        log = self._db.execute(stmt).scalar_one_or_none()
        if not log:
            return None

        for key, value in log_data.items():
            setattr(log, key, value)

        self._db.commit()
        self._db.refresh(log)
        return log

    def get_log_by_id(self, log_id: uuid.UUID) -> DeliveryLog | None:
        """
        Busca um log de entrega pelo ID.

        Args:
            log_id: ID (UUID) do log.

        Returns:
            DeliveryLog encontrado ou None.
        """
        stmt = select(DeliveryLog).where(DeliveryLog.id == log_id)
        return self._db.execute(stmt).scalar_one_or_none()

    def get_logs_by_execution(self, execution_id: uuid.UUID) -> list[DeliveryLog]:
        """
        Busca todos os logs de entrega de uma execucao.

        Args:
            execution_id: ID (UUID) da execucao.

        Returns:
            Lista de logs de entrega da execucao.
        """
        stmt = select(DeliveryLog).where(
            DeliveryLog.execution_id == execution_id,
        ).order_by(DeliveryLog.created_at.desc())

        return list(self._db.execute(stmt).scalars().all())

    def get_logs_by_config(self, config_id: uuid.UUID) -> list[DeliveryLog]:
        """
        Busca todos os logs de entrega de uma configuracao.

        Args:
            config_id: ID (UUID) da configuracao de entrega.

        Returns:
            Lista de logs de entrega da configuracao.
        """
        stmt = select(DeliveryLog).where(
            DeliveryLog.delivery_config_id == config_id,
        ).order_by(DeliveryLog.created_at.desc())

        return list(self._db.execute(stmt).scalars().all())
