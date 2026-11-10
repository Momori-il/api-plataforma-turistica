from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


def business_today():
    """Fecha de operación del MVP en Posadas (UTC-03:00)."""
    return datetime.now(timezone(timedelta(hours=-3))).date()


class HabitacionInput(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    nombre: str = Field(min_length=2, max_length=100)
    capacidad: int = Field(gt=0, le=1000)
    cantidad_total: int = Field(gt=0, le=1000)
    precio_noche: Decimal = Field(gt=0, max_digits=12, decimal_places=2)

    @field_validator("nombre", mode="before")
    @classmethod
    def limpiar_nombre(cls, value):
        return value.strip() if isinstance(value, str) else value


class HabitacionPublicResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    hotel_id: int
    nombre: str
    capacidad: int
    precio_noche: Decimal
    moneda: Literal["ARS"] = "ARS"


class HabitacionGestionResponse(HabitacionPublicResponse):
    cantidad_total: int
    estado: Literal["ACTIVO", "INACTIVO"]


class HabitacionEstadoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    estado: Literal["ACTIVO", "INACTIVO"]


class DisponibilidadParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fecha_desde: date
    fecha_hasta: date
    personas: int = Field(default=1, ge=1, le=1000)
    cantidad_habitaciones: int = Field(default=1, ge=1, le=1000)

    @model_validator(mode="after")
    def validar_estadia(self):
        if self.fecha_desde < business_today():
            raise ValueError("La entrada no puede ser anterior a la fecha actual de Posadas")
        nights = (self.fecha_hasta - self.fecha_desde).days
        if not 1 <= nights <= 365:
            raise ValueError("La estadía debe tener entre 1 y 365 noches")
        return self


class HabitacionDisponibilidadResponse(HabitacionPublicResponse):
    habitaciones_disponibles: int
    cantidad_habitaciones: int
    personas: int
    noches: int
    precio_total: Decimal
    disponible: bool


class DisponibilidadResponse(BaseModel):
    hotel_id: int
    fecha_desde: date
    fecha_hasta: date
    noches: int
    personas: int
    cantidad_habitaciones: int
    habitaciones: list[HabitacionDisponibilidadResponse]
