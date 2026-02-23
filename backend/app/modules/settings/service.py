import logging
import smtplib

from app.modules.settings.repository import SettingRepository
from app.modules.settings.schemas import SMTPConfigSchema, SettingsGroupResponse
from app.shared.utils import decrypt_value, encrypt_value

logger = logging.getLogger(__name__)

# Descricoes padrao para chaves SMTP
SMTP_KEY_DESCRIPTIONS: dict[str, str] = {
    'smtp_host': 'Host do servidor SMTP',
    'smtp_port': 'Porta do servidor SMTP',
    'smtp_username': 'Usuario para autenticacao SMTP',
    'smtp_password': 'Senha para autenticacao SMTP',
    'smtp_use_tls': 'Usar TLS na conexao SMTP (true/false)',
    'smtp_sender_email': 'Endereco de email do remetente',
}


class SettingService:
    """
    Servico de configuracoes do sistema.

    Contem a logica de negocio para gerenciar configuracoes,
    incluindo criptografia/descriptografia de valores e teste de conexao SMTP.
    """

    def __init__(self, repository: SettingRepository) -> None:
        """Inicializa o servico com o repositorio de configuracoes."""
        self._repository = repository

    def get_settings(self, category: str) -> SettingsGroupResponse:
        """
        Obtem todas as configuracoes de uma categoria com valores descriptografados.

        Args:
            category: Categoria das configuracoes (ex: smtp, general).

        Returns:
            Resposta com categoria e dicionario de configuracoes descriptografadas.
        """
        settings_list = self._repository.get_by_category(category)

        decrypted_settings: dict[str, str] = {}
        for setting in settings_list:
            try:
                decrypted_settings[setting.key] = decrypt_value(setting.encrypted_value)
            except Exception:
                # Se nao conseguir descriptografar, registra o erro mas nao expoe
                logger.warning(
                    'Nao foi possivel descriptografar a configuracao: %s',
                    setting.key,
                )
                decrypted_settings[setting.key] = ''

        return SettingsGroupResponse(
            category=category,
            settings=decrypted_settings,
        )

    def update_settings(self, category: str, data: dict[str, str]) -> SettingsGroupResponse:
        """
        Atualiza configuracoes de uma categoria (criptografa e faz upsert de cada chave).

        Args:
            category: Categoria das configuracoes.
            data: Dicionario com pares chave-valor a serem atualizados.

        Returns:
            Resposta com categoria e dicionario de configuracoes atualizadas.
        """
        # Obtem descricoes padrao para chaves conhecidas
        for key, value in data.items():
            encrypted = encrypt_value(value)
            description = SMTP_KEY_DESCRIPTIONS.get(key) if category == 'smtp' else None
            self._repository.upsert(
                key=key,
                encrypted_value=encrypted,
                category=category,
                description=description,
            )

        # Retorna as configuracoes atualizadas
        return self.get_settings(category)

    def get_smtp_config(self) -> dict[str, str]:
        """
        Obtem a configuracao SMTP descriptografada.

        Returns:
            Dicionario com configuracoes SMTP (host, port, username, password,
            use_tls, sender_email).
        """
        settings_response = self.get_settings('smtp')
        return settings_response.settings

    def test_smtp_connection(self, config: SMTPConfigSchema) -> bool:
        """
        Testa a conexao SMTP com as configuracoes fornecidas.

        Tenta conectar ao servidor SMTP, fazer login e desconectar.

        Args:
            config: Configuracoes SMTP para teste.

        Returns:
            True se a conexao foi bem-sucedida, False caso contrario.
        """
        try:
            if config.use_tls:
                with smtplib.SMTP(config.host, config.port, timeout=10) as server:
                    server.ehlo()
                    server.starttls()
                    server.ehlo()
                    server.login(config.username, config.password)
            else:
                with smtplib.SMTP(config.host, config.port, timeout=10) as server:
                    server.ehlo()
                    if config.username and config.password:
                        server.login(config.username, config.password)

            logger.info('Teste de conexao SMTP bem-sucedido para %s:%d', config.host, config.port)
            return True

        except smtplib.SMTPAuthenticationError:
            logger.warning(
                'Falha de autenticacao SMTP para %s:%d',
                config.host,
                config.port,
            )
            return False

        except smtplib.SMTPException as e:
            logger.warning(
                'Erro SMTP ao testar conexao %s:%d - %s',
                config.host,
                config.port,
                str(e),
            )
            return False

        except Exception as e:
            logger.warning(
                'Erro inesperado ao testar conexao SMTP %s:%d - %s',
                config.host,
                config.port,
                str(e),
            )
            return False
