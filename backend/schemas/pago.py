from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from schemas.reserva import ReservaResponse

ResultadoPago = Literal["APROBADO", "RECHAZADO"]


class PagoSimuladoInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    clave_idempotencia: UUID
    resultado: ResultadoPago


class PagoResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    reserva_id: int
    clave_idempotencia: UUID
    importe: Decimal
    moneda: Literal["ARS"]
    estado: ResultadoPago
    creado_en: AwareDatetime
    simulado: Literal[True] = True

    @field_validator("creado_en", mode="before")
    @classmethod
    def fecha_utc(cls, value):
        return value.replace(tzinfo=timezone.utc) if isinstance(value, datetime) and value.tzinfo is None else value


class PagoOperacionResponse(BaseModel):
    pago: PagoResponse
    reserva: ReservaResponse


class PagoListParams(BaseModel):
    model_config = ConfigDict(extra="forbid")
    offset: int = Field(default=0, ge=0)
    limit: int = Field(default=50, ge=1, le=100)


class PagoPage(BaseModel):
    items: list[PagoResponse]
    total: int
    offset: int
    limit: int
