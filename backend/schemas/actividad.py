from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator, model_validator

from schemas.habitacion import business_today

POSADAS_TZ = timezone(timedelta(hours=-3))


class ActividadInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    nombre: str = Field(min_length=2, max_length=150)
    descripcion: str | None = Field(default=None, max_length=2000)
    ubicacion: str = Field(min_length=2, max_length=255)
    duracion_minutos: int = Field(ge=1, le=1440)
    precio_persona: Decimal = Field(gt=0, max_digits=12, decimal_places=2)

    @field_validator("nombre", "ubicacion", mode="before")
    @classmethod
    def limpiar_texto(cls, value):
        return value.strip() if isinstance(value, str) else value


class ActividadResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    descripcion: str | None
    ubicacion: str
    duracion_minutos: int
    precio_persona: Decimal
    moneda: Literal["ARS"] = "ARS"


class ActividadGestionResponse(ActividadResponse):
    prestador_id: int
    estado: Literal["ACTIVO", "INACTIVO"]
    aprobacion: Literal["PENDIENTE", "APROBADA", "RECHAZADA"]


class EstadoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    estado: Literal["ACTIVO", "INACTIVO"]


class AprobacionInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    aprobacion: Literal["PENDIENTE", "APROBADA", "RECHAZADA"]


class PrestadorInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prestador_id: int = Field(gt=0, le=2147483647)


class TurnoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inicio: AwareDatetime
    cupo_total: int = Field(ge=1, le=1000)

    @field_validator("inicio", mode="before")
    @classmethod
    def exigir_horario_explicito(cls, value):
        if not isinstance(value, (str, datetime)):
            raise ValueError("El inicio requiere fecha y hora ISO 8601 con zona horaria")
        return value

    @field_validator("inicio")
    @classmethod
    def a_utc(cls, value):
        try:
            return value.astimezone(timezone.utc)
        except (OverflowError, ValueError):
            raise ValueError("El inicio está fuera del rango horario permitido")


class TurnoGestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    actividad_id: int
    inicio: AwareDatetime
    fin: AwareDatetime
    cupo_total: int
    estado: Literal["ACTIVO", "INACTIVO"]

    @field_validator("inicio", "fin", mode="before")
    @classmethod
    def hora_guardada_en_utc(cls, value):
        if isinstance(value, datetime) and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value


class TurnoPublicResponse(BaseModel):
    id: int
    actividad_id: int
    inicio: AwareDatetime
    fin: AwareDatetime
    cupos_disponibles: int
    personas: int
    precio_persona: Decimal
    precio_total: Decimal
    moneda: Literal["ARS"] = "ARS"
    disponible: bool


class TurnoSearchParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fecha_desde: date = Field(default_factory=business_today)
    fecha_hasta: date | None = None
    personas: int = Field(default=1, ge=1, le=1000)

    @model_validator(mode="after")
    def validar_periodo(self):
        if self.fecha_desde < business_today():
            raise ValueError("La búsqueda no puede empezar antes de la fecha actual de Posadas")
        if self.fecha_hasta is None:
            try:
                self.fecha_hasta = self.fecha_desde + timedelta(days=365)
            except OverflowError:
                raise ValueError("El período está fuera del rango permitido")
        if not 1 <= (self.fecha_hasta - self.fecha_desde).days <= 365:
            raise ValueError("La búsqueda debe abarcar entre 1 y 365 días")
        return self


class TurnoSearchResponse(BaseModel):
    actividad_id: int
    fecha_desde: date
    fecha_hasta: date
    personas: int
    turnos: list[TurnoPublicResponse]
