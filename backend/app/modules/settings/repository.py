from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.modules.settings.models import Setting


class SettingRepository:
    """
    Repositorio de acesso a dados de configuracoes do sistema.

    Responsavel por operacoes de leitura e escrita na tabela settings.
    Nao contem logica de negocio — apenas acesso a dados.
    """

    def __init__(self, db: Session) -> None:
        """Inicializa o repositorio com a sessao do banco."""
        self._db = db

    def get_by_key(self, key: str) -> Setting | None:
        """
        Busca uma configuracao pela chave.

        Args:
            key: Chave unica da configuracao.

        Returns:
            Configuracao encontrada ou None.
        """
        stmt = select(Setting).where(Setting.key == key)
        return self._db.execute(stmt).scalar_one_or_none()

    def get_by_category(self, category: str) -> list[Setting]:
        """
        Busca todas as configuracoes de uma categoria.

        Args:
            category: Categoria das configuracoes (ex: smtp, general).

        Returns:
            Lista de configuracoes da categoria.
        """
        stmt = (
            select(Setting)
            .where(Setting.category == category)
            .order_by(Setting.key)
        )
        return list(self._db.execute(stmt).scalars().all())

    def upsert(
        self,
        key: str,
        encrypted_value: str,
        category: str,
        description: str | None = None,
    ) -> Setting:
        """
        Cria ou atualiza uma configuracao (upsert).

        Se a chave ja existe, atualiza o valor criptografado.
        Caso contrario, cria um novo registro.

        Args:
            key: Chave unica da configuracao.
            encrypted_value: Valor criptografado da configuracao.
            category: Categoria da configuracao.
            description: Descricao opcional da configuracao.

        Returns:
            Configuracao criada ou atualizada.
        """
        existing = self.get_by_key(key)

        if existing:
            # Atualiza o valor existente
            existing.encrypted_value = encrypted_value
            existing.category = category
            if description is not None:
                existing.description = description
            self._db.commit()
            self._db.refresh(existing)
            return existing
        else:
            # Cria nova configuracao
            setting = Setting(
                key=key,
                encrypted_value=encrypted_value,
                category=category,
                description=description,
            )
            self._db.add(setting)
            self._db.commit()
            self._db.refresh(setting)
            return setting

    def delete_by_key(self, key: str) -> bool:
        """
        Exclui permanentemente uma configuracao pela chave.

        Args:
            key: Chave da configuracao a ser excluida.

        Returns:
            True se a configuracao foi excluida, False se nao encontrada.
        """
        setting = self.get_by_key(key)
        if not setting:
            return False

        self._db.delete(setting)
        self._db.commit()
        return True
