from datetime import datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator


class Rol(str, Enum):
    TURISTA = "TURISTA"
    PRESTADOR = "PRESTADOR"
    ADMIN = "ADMIN"


class EmailInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: Annotated[EmailStr, Field(max_length=254)]

    @field_validator("email", mode="before")
    @classmethod
    def normalizar_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class RegistroInput(EmailInput):
    nombre: str = Field(min_length=2, max_length=100)
    password: SecretStr = Field(min_length=12, max_length=128)
    rol: Literal["TURISTA", "PRESTADOR"] = "TURISTA"

    @field_validator("nombre", mode="before")
    @classmethod
    def limpiar_nombre(cls, value):
        return value.strip() if isinstance(value, str) else value


class LoginInput(EmailInput):
    password: SecretStr = Field(min_length=1, max_length=128)


class UsuarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    email: EmailStr
    rol: Rol
    activo: bool
    creado_en: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
