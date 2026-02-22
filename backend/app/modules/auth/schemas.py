import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, field_validator


class LoginRequest(BaseModel):
    """Schema de requisicao de login."""

    email: EmailStr
    password: str

    @field_validator('password')
    @classmethod
    def password_not_empty(cls, v: str) -> str:
        """Valida que a senha nao esta vazia."""
        if not v or not v.strip():
            raise ValueError('A senha nao pode estar vazia')
        return v


class TokenResponse(BaseModel):
    """Schema de resposta com tokens JWT."""

    access_token: str
    refresh_token: str
    token_type: str = 'bearer'


class RefreshRequest(BaseModel):
    """Schema de requisicao de refresh token."""

    refresh_token: str


class UserResponse(BaseModel):
    """Schema de resposta com dados do usuario."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    name: str
    is_active: bool
    created_at: datetime


class UserCreate(BaseModel):
    """Schema para criacao de usuario (usado no seed)."""

    email: EmailStr
    password: str
    name: str

    @field_validator('password')
    @classmethod
    def password_min_length(cls, v: str) -> str:
        """Valida que a senha tem pelo menos 6 caracteres."""
        if len(v) < 6:
            raise ValueError('A senha deve ter pelo menos 6 caracteres')
        return v

    @field_validator('name')
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        """Valida que o nome nao esta vazio."""
        if not v or not v.strip():
            raise ValueError('O nome nao pode estar vazio')
        return v.strip()
