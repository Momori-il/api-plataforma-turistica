from datetime import datetime, timezone
from typing import Generic, Literal, TypeVar

from pydantic import AwareDatetime, BaseModel, ConfigDict, EmailStr, Field, field_validator, model_validator

from schemas.auth import Rol, UsuarioResponse
from schemas.reserva import EstadoReserva, ReservaResponse

T = TypeVar("T")


class Paginacion(BaseModel):
    model_config = ConfigDict(extra="forbid")
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=100)


class Pagina(BaseModel, Generic[T]):
    items: list[T]
    total: int
    offset: int
    limit: int


class ReservasGestionParams(Paginacion):
    estado: EstadoReserva | None = None
    tipo: Literal["HOTEL", "ACTIVIDAD"] | None = None
    hotel_id: int | None = Field(default=None, gt=0, le=2147483647)
    actividad_id: int | None = Field(default=None, gt=0, le=2147483647)
    turista_id: int | None = Field(default=None, gt=0, le=2147483647)
    prestador_id: int | None = Field(default=None, gt=0, le=2147483647)

    @model_validator(mode="after")
    def filtros_compatibles(self):
        if self.hotel_id is not None and (self.actividad_id is not None or self.tipo == "ACTIVIDAD"):
            raise ValueError("hotel_id requiere reservas de hotel")
        if self.actividad_id is not None and self.tipo == "HOTEL":
            raise ValueError("actividad_id requiere reservas de actividad")
        return self


class PublicacionesGestionParams(Paginacion):
    estado: Literal["ACTIVO", "INACTIVO"] | None = None
    aprobacion: Literal["PENDIENTE", "APROBADA", "RECHAZADA"] | None = None
    prestador_id: int | None = Field(default=None, gt=0, le=2147483647)


class TuristaContacto(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    email: EmailStr


class ReservaGestionResponse(ReservaResponse):
    turista: TuristaContacto
    prestador_id: int | None


class UsuariosGestionParams(Paginacion):
    rol: Rol | None = None
    activo: bool | None = None


class UsuarioEstadoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    activo: bool = Field(strict=True)


class UsuarioAdminResponse(UsuarioResponse):
    creado_en: AwareDatetime

    @field_validator("creado_en", mode="before")
    @classmethod
    def fecha_utc(cls, value):
        return value.replace(tzinfo=timezone.utc) if isinstance(value, datetime) and value.tzinfo is None else value
