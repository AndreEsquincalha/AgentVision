import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.modules.auth.models import UserRole
from app.shared.security import sanitize_text, validate_password_strength


class LoginRequest(BaseModel):
    """Schema de requisicao de login."""

    email: EmailStr
    password: str

    @field_validator('email')
    @classmethod
    def email_normalized(cls, v: EmailStr) -> str:
        """Normaliza o email."""
        return sanitize_text(str(v)).lower()

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
    role: str
    created_at: datetime


class UserCreate(BaseModel):
    """Schema para criacao de usuario (usado no seed)."""

    email: EmailStr
    password: str
    name: str
    role: UserRole = Field(
        default=UserRole.admin,
        description='Role do usuario (admin, operator, viewer)',
    )

    @field_validator('password')
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Valida requisitos de senha forte."""
        return validate_password_strength(v)

    @field_validator('name')
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        """Valida que o nome nao esta vazio."""
        if not v or not v.strip():
            raise ValueError('O nome nao pode estar vazio')
        return sanitize_text(v)


class PasswordChange(BaseModel):
    """Schema para troca de senha."""

    current_password: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=1)

    @field_validator('new_password')
    @classmethod
    def new_password_strength(cls, v: str) -> str:
        """Valida requisitos de senha forte."""
        return validate_password_strength(v)


class LogoutRequest(BaseModel):
    """Schema de logout opcional."""

    refresh_token: str | None = Field(
        None,
        description='Refresh token para revogacao opcional',
    )


class UnlockAccountRequest(BaseModel):
    """Schema para desbloqueio manual de conta."""

    email: EmailStr

    @field_validator('email')
    @classmethod
    def unlock_email_normalized(cls, v: EmailStr) -> str:
        """Normaliza o email."""
        return sanitize_text(str(v)).lower()
