from sqlalchemy import CheckConstraint, Column, ForeignKey, Index, Integer, String, Float
from sqlalchemy.orm import relationship
from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Literal, Optional
from database.connection import Base

# --- MODELO DE BASE DE DATOS (SQLAlchemy) ---
class HotelDB(Base):
    __tablename__ = "hoteles"
    __table_args__ = (
        CheckConstraint("aprobacion IN ('PENDIENTE', 'APROBADA', 'RECHAZADA')", name="CK_hoteles_aprobacion"),
        Index("IX_hoteles_prestador", "prestador_id", "estado", "aprobacion"),
    )

    id = Column(Integer, primary_key=True, index=True)
    nombre = Column(String(100), nullable=False)
    zona_id = Column(Integer, nullable=False)
    precio_base = Column(Float, nullable=False)
    descripcion = Column(String(255))
    direccion = Column(String(200))
    categoria = Column(Integer)
    calificacion = Column(Float, default=0.0)
    servicio = Column(String(255))
    estado = Column(String(20), nullable=False, default="ACTIVO")
    prestador_id = Column(Integer, ForeignKey("usuarios.id", name="FK_hoteles_prestador"))
    aprobacion = Column(String(20), nullable=False, default="PENDIENTE")
    prestador = relationship("UsuarioDB")

# --- ESQUEMAS DE VALIDACIÓN (Pydantic) ---
class HotelBase(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    nombre: str = Field(..., min_length=2, max_length=100, description="Nombre del alojamiento")
    zona_id: int = Field(..., gt=0, le=2147483647, description="ID de la zona")
    precio_base: float = Field(..., gt=0, description="Precio por noche")
    descripcion: Optional[str] = Field(None, max_length=255)
    direccion: Optional[str] = Field(None, max_length=200)
    categoria: Optional[int] = Field(None, ge=1, le=5)
    calificacion: Optional[float] = Field(0.0, ge=0, le=10)
    servicio: Optional[str] = Field(None, max_length=255)

    @field_validator("nombre", mode="before")
    @classmethod
    def limpiar_nombre(cls, value):
        return value.strip() if isinstance(value, str) else value

class HotelCreate(HotelBase):
    pass

class HotelResponse(HotelBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid", allow_inf_nan=False)
    id: int
    estado: Literal["ACTIVO", "INACTIVO"]


class HotelGestionResponse(HotelResponse):
    prestador_id: Optional[int]
    aprobacion: Literal["PENDIENTE", "APROBADA", "RECHAZADA"]


class HotelEstadoUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    estado: Literal["ACTIVO", "INACTIVO"]


class HotelAprobacionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    aprobacion: Literal["PENDIENTE", "APROBADA", "RECHAZADA"]


class HotelPrestadorUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    prestador_id: int = Field(gt=0, le=2147483647)
