from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from schemas.habitacion import DisponibilidadParams

EstadoReserva = Literal["PENDIENTE_PAGO", "CONFIRMADA", "CANCELADA", "EXPIRADA"]


class ReservaHotelInput(DisponibilidadParams):
    hotel_id: int = Field(gt=0, le=2147483647)
    habitacion_id: int = Field(gt=0, le=2147483647)


class ReservaActividadInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    actividad_id: int = Field(gt=0, le=2147483647)
    turno_id: int = Field(gt=0, le=2147483647)
    personas: int = Field(ge=1, le=1000)


class ReservaListParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    estado: EstadoReserva | None = None
    tipo: Literal["HOTEL", "ACTIVIDAD"] | None = None
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=100)


class AlojamientoReservado(BaseModel):
    hotel_id: int
    hotel_nombre: str
    habitacion_nombre: str


class ActividadReservada(BaseModel):
    actividad_id: int
    nombre: str
    inicio: AwareDatetime
    fin: AwareDatetime


class ReservaResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    turista_id: int
    tipo: Literal["HOTEL", "ACTIVIDAD"]
    habitacion_id: int | None
    turno_id: int | None
    fecha_desde: date | None
    fecha_hasta: date | None
    cantidad_habitaciones: int | None
    personas: int
    precio_unitario: Decimal
    total: Decimal
    moneda: Literal["ARS"]
    estado: EstadoReserva
    creado_en: AwareDatetime
    vence_en: AwareDatetime | None
    cancelada_en: AwareDatetime | None
    alojamiento: AlojamientoReservado | None = None
    actividad: ActividadReservada | None = None

    @field_validator("creado_en", "vence_en", "cancelada_en", mode="before")
    @classmethod
    def fecha_utc(cls, value):
        return value.replace(tzinfo=timezone.utc) if isinstance(value, datetime) and value.tzinfo is None else value


class ReservaPage(BaseModel):
    items: list[ReservaResponse]
    total: int
    offset: int
    limit: int
