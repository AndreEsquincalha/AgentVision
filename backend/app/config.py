from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuracoes da aplicacao carregadas de variaveis de ambiente."""

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        case_sensitive=False,
    )

    # -------------------------------------------------------------------------
    # PostgreSQL
    # -------------------------------------------------------------------------
    postgres_host: str = 'localhost'
    postgres_port: int = 5432
    postgres_user: str = 'agentvision'
    postgres_password: str = 'agentvision_secret_password'
    postgres_db: str = 'agentvision'

    @property
    def database_url(self) -> str:
        """URL de conexao com o PostgreSQL."""
        return (
            f'postgresql://{self.postgres_user}:{self.postgres_password}'
            f'@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}'
        )

    # -------------------------------------------------------------------------
    # Redis
    # -------------------------------------------------------------------------
    redis_url: str = 'redis://localhost:6379/0'

    # -------------------------------------------------------------------------
    # MinIO (S3-compatible)
    # -------------------------------------------------------------------------
    minio_endpoint: str = 'localhost:9000'
    minio_public_endpoint: str = ''
    minio_access_key: str = 'minioadmin'
    minio_secret_key: str = 'minioadmin_secret_password'
    minio_bucket: str = 'agentvision'
    minio_use_ssl: bool = False

    # -------------------------------------------------------------------------
    # JWT
    # -------------------------------------------------------------------------
    jwt_secret_key: str = 'change-me-to-a-long-random-secret-key'
    jwt_algorithm: str = 'HS256'
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_days: int = 7

    # -------------------------------------------------------------------------
    # Criptografia (Fernet)
    # -------------------------------------------------------------------------
    encryption_key: str = 'change-me-to-a-valid-fernet-key'
    encryption_keys: str = ''

    # -------------------------------------------------------------------------
    # CORS
    # -------------------------------------------------------------------------
    cors_origins: str = 'http://localhost:3000'

    @property
    def cors_origins_list(self) -> list[str]:
        """Retorna lista de origens permitidas para CORS."""
        return [origin.strip() for origin in self.cors_origins.split(',')]

    # -------------------------------------------------------------------------
    # Admin Seed
    # -------------------------------------------------------------------------
    admin_email: str = 'admin@agentvision.com'
    admin_password: str = 'admin123'
    admin_name: str = 'Administrador'


# Instancia global de configuracoes
settings = Settings()
