from pydantic import BaseModel, ConfigDict, Field, field_validator


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


class SettingUpdate(BaseModel):
    """Schema para atualizacao do valor de uma configuracao."""

    value: str = Field(
        ...,
        min_length=1,
        description='Novo valor da configuracao (sera criptografado)',
    )


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
        return v


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
