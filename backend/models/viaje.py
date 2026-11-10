from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import Column, Date, ForeignKey, Integer, String

from database.connection import Base


# =========================================================
# MODELOS DE BASE DE DATOS - SQLAlchemy
# =========================================================

class ViajeDB(Base):
    __tablename__ = "viajes"

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    fecha_inicio = Column(Date, nullable=False)
    fecha_fin = Column(Date, nullable=False)
    estado = Column(String(20), nullable=False, default="PLANIFICADO")


class ViajeHotelDB(Base):
    __tablename__ = "viaje_hoteles"

    id = Column(Integer, primary_key=True, index=True)

    viaje_id = Column(
        Integer,
        ForeignKey("viajes.id"),
        nullable=False
    )

    hotel_id = Column(
        Integer,
        ForeignKey("hoteles.id"),
        nullable=False
    )

    fecha_desde = Column(Date, nullable=False)
    fecha_hasta = Column(Date, nullable=False)

    estado = Column(
        String(20),
        nullable=False,
        default="ACTIVO"
    )


# =========================================================
# ESQUEMAS PYDANTIC - VIAJE
# =========================================================

class ViajeCreate(BaseModel):
    nombre: str = Field(
        ...,
        min_length=2,
        max_length=100,
        description="Nombre descriptivo del viaje"
    )

    fecha_inicio: date
    fecha_fin: date

    @model_validator(mode="after")
    def validar_fechas(self):
        if self.fecha_inicio >= self.fecha_fin:
            raise ValueError(
                "fecha_inicio debe ser anterior a fecha_fin"
            )

        return self


class ViajeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    nombre: str
    fecha_inicio: date
    fecha_fin: date
    estado: str


# =========================================================
# ESQUEMAS PYDANTIC - VIAJE HOTEL
# =========================================================

class ViajeHotelCreate(BaseModel):
    hotel_id: int = Field(
        ...,
        gt=0,
        description="ID del hotel que se asociará al viaje"
    )

    fecha_desde: date
    fecha_hasta: date

    @model_validator(mode="after")
    def validar_fechas(self):
        if self.fecha_desde >= self.fecha_hasta:
            raise ValueError(
                "fecha_desde debe ser anterior a fecha_hasta"
            )

        return self


class ViajeHotelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    viaje_id: int
    hotel_id: int
    fecha_desde: date
    fecha_hasta: date
    estado: str
