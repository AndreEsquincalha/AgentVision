from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.shared.security import sanitize_text


class SettingCreate(BaseModel):
    """Schema para criacao de uma configuracao."""

    key: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description='Chave da configuracao',
    )
    value: str = Field(
        ...,
        min_length=1,
        description='Valor da configuracao (sera criptografado)',
    )
    category: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description='Categoria da configuracao (ex: smtp, general)',
    )
    description: str | None = Field(
        None,
        description='Descricao da configuracao',
    )

    @field_validator('key')
    @classmethod
    def key_sanitized(cls, v: str) -> str:
        """Sanitiza chave."""
        return sanitize_text(v)

    @field_validator('value')
    @classmethod
    def value_sanitized(cls, v: str) -> str:
        """Sanitiza valor."""
        return sanitize_text(v)

    @field_validator('category')
    @classmethod
    def category_sanitized(cls, v: str) -> str:
        """Sanitiza categoria."""
        return sanitize_text(v)

    @field_validator('description')
    @classmethod
    def description_sanitized(cls, v: str | None) -> str | None:
        """Sanitiza descricao."""
        if v is None:
            return v
        return sanitize_text(v)


class SettingUpdate(BaseModel):
    """Schema para atualizacao do valor de uma configuracao."""

    value: str = Field(
        ...,
        min_length=1,
        description='Novo valor da configuracao (sera criptografado)',
    )

    @field_validator('value')
    @classmethod
    def value_sanitized(cls, v: str) -> str:
        """Sanitiza valor."""
        return sanitize_text(v)


class SettingResponse(BaseModel):
    """
    Schema de resposta com dados de uma configuracao.

    Nao expoe o valor criptografado em texto puro.
    Em vez disso, indica se a configuracao possui valor
    atraves do campo has_value.
    """

    model_config = ConfigDict(from_attributes=True)

    key: str
    category: str
    description: str | None = None
    has_value: bool = False


class SettingsGroupResponse(BaseModel):
    """
    Schema de resposta com configuracoes agrupadas por categoria.

    Retorna um dicionario com pares chave-valor descriptografados.
    """

    category: str
    settings: dict[str, str]


class SettingsBulkUpdate(BaseModel):
    """
    Schema para atualizacao em lote de configuracoes de uma categoria.

    Recebe um dicionario com pares chave-valor a serem atualizados.
    """

    settings: dict[str, str] = Field(
        ...,
        description='Dicionario de configuracoes (chave -> valor)',
    )

    @field_validator('settings')
    @classmethod
    def settings_not_empty(cls, v: dict[str, str]) -> dict[str, str]:
        """Valida que o dicionario de configuracoes nao esta vazio."""
        if not v:
            raise ValueError('O dicionario de configuracoes nao pode estar vazio')
        cleaned: dict[str, str] = {}
        for key, value in v.items():
            cleaned[sanitize_text(key)] = sanitize_text(value)
        return cleaned


class LogLevelUpdate(BaseModel):
    """Schema para atualizacao de log levels em runtime."""

    levels: dict[str, str] = Field(
        ...,
        description='Dicionario de modulo -> nivel (ex: {"app.modules.agents": "DEBUG"})',
    )

    @field_validator('levels')
    @classmethod
    def validate_levels(cls, v: dict[str, str]) -> dict[str, str]:
        """Valida que os niveis sao validos."""
        valid_levels = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
        cleaned: dict[str, str] = {}
        for module, level in v.items():
            level_upper = level.strip().upper()
            if level_upper not in valid_levels:
                raise ValueError(
                    f'Nivel invalido "{level}" para modulo "{module}". '
                    f'Valores permitidos: {", ".join(sorted(valid_levels))}'
                )
            cleaned[sanitize_text(module.strip())] = level_upper
        return cleaned


class LogLevelResponse(BaseModel):
    """Schema de resposta com log levels atuais."""

    levels: dict[str, str]
    global_level: str


class SMTPConfigSchema(BaseModel):
    """
    Schema para configuracao e teste de conexao SMTP.

    Usado no endpoint de teste de conexao SMTP.
    """

    host: str = Field(
        ...,
        min_length=1,
        description='Host do servidor SMTP',
    )
    port: int = Field(
        ...,
        gt=0,
        le=65535,
        description='Porta do servidor SMTP',
    )
    username: str = Field(
        '',
        description='Usuario para autenticacao SMTP (opcional)',
    )
    password: str = Field(
        '',
        description='Senha para autenticacao SMTP (opcional)',
    )
    use_tls: bool = Field(
        True,
        description='Se deve usar TLS na conexao',
    )
    sender_email: str = Field(
        ...,
        min_length=1,
        description='Endereco de email do remetente',
    )

    @field_validator('host', 'username', 'password', 'sender_email')
    @classmethod
    def smtp_fields_sanitized(cls, v: str) -> str:
        """Sanitiza campos SMTP."""
        return sanitize_text(v)
