"""Persistencia del MVP. Fechas y horas sin zona representan UTC."""

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, CheckConstraint, Column, Date, DateTime, ForeignKey,
    ForeignKeyConstraint, Index, Integer, Numeric, String, Unicode,
    UniqueConstraint, text,
)
from sqlalchemy.dialects.mssql import DATETIME2, NVARCHAR
from sqlalchemy.orm import relationship

from database.connection import Base

UTC_DATETIME = DateTime().with_variant(DATETIME2(precision=6), "mssql")

def utc_now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class UsuarioDB(Base):
    __tablename__ = "usuarios"
    __table_args__ = (
        UniqueConstraint("email", name="UQ_usuarios_email"),
        CheckConstraint("rol IN ('TURISTA', 'PRESTADOR', 'ADMIN')", name="CK_usuarios_rol"),
    )

    id = Column(Integer, primary_key=True)
    nombre = Column(Unicode(100), nullable=False)
    email = Column(
        String(254, collation="NOCASE").with_variant(
            NVARCHAR(254, collation="Latin1_General_100_CI_AS"), "mssql"
        ), nullable=False,
    )
    password_hash = Column(String(255), nullable=False)
    rol = Column(String(20), nullable=False, default="TURISTA")
    activo = Column(Boolean, nullable=False, default=True)
    creado_en = Column(UTC_DATETIME, nullable=False, default=utc_now)


class HabitacionDB(Base):
    """Inventario agrupado por tipo de habitación de un hotel."""

    __tablename__ = "habitaciones"
    __table_args__ = (
        UniqueConstraint("hotel_id", "nombre", name="UQ_habitaciones_hotel_nombre"),
        CheckConstraint("capacidad > 0", name="CK_habitaciones_capacidad"),
        CheckConstraint("cantidad_total > 0", name="CK_habitaciones_cantidad"),
        CheckConstraint("precio_noche > 0", name="CK_habitaciones_precio"),
        CheckConstraint("estado IN ('ACTIVO', 'INACTIVO')", name="CK_habitaciones_estado"),
    )

    id = Column(Integer, primary_key=True)
    hotel_id = Column(Integer, ForeignKey("hoteles.id", name="FK_habitaciones_hotel"), nullable=False)
    nombre = Column(Unicode(100), nullable=False)
    capacidad = Column(Integer, nullable=False)
    cantidad_total = Column(Integer, nullable=False)
    precio_noche = Column(Numeric(12, 2), nullable=False)
    estado = Column(String(20), nullable=False, default="ACTIVO")
    hotel = relationship("HotelDB")


class ActividadDB(Base):
    __tablename__ = "actividades"
    __table_args__ = (
        CheckConstraint("duracion_minutos > 0", name="CK_actividades_duracion"),
        CheckConstraint("precio_persona > 0", name="CK_actividades_precio"),
        CheckConstraint("estado IN ('ACTIVO', 'INACTIVO')", name="CK_actividades_estado"),
        CheckConstraint("aprobacion IN ('PENDIENTE', 'APROBADA', 'RECHAZADA')", name="CK_actividades_aprobacion"),
        Index("IX_actividades_prestador", "prestador_id", "estado", "aprobacion"),
    )

    id = Column(Integer, primary_key=True)
    prestador_id = Column(Integer, ForeignKey("usuarios.id", name="FK_actividades_prestador"), nullable=False)
    nombre = Column(Unicode(150), nullable=False)
    descripcion = Column(Unicode(2000))
    ubicacion = Column(Unicode(255), nullable=False)
    duracion_minutos = Column(Integer, nullable=False)
    precio_persona = Column(Numeric(12, 2), nullable=False)
    estado = Column(String(20), nullable=False, default="ACTIVO")
    aprobacion = Column(String(20), nullable=False, default="PENDIENTE")
    prestador = relationship("UsuarioDB")


class ActividadTurnoDB(Base):
    __tablename__ = "actividad_turnos"
    __table_args__ = (
        UniqueConstraint("actividad_id", "inicio", name="UQ_turnos_actividad_inicio"),
        CheckConstraint("inicio < fin", name="CK_turnos_fechas"),
        CheckConstraint("cupo_total > 0", name="CK_turnos_cupo"),
        CheckConstraint("estado IN ('ACTIVO', 'INACTIVO')", name="CK_turnos_estado"),
    )

    id = Column(Integer, primary_key=True)
    actividad_id = Column(Integer, ForeignKey("actividades.id", name="FK_turnos_actividad"), nullable=False)
    inicio = Column(UTC_DATETIME, nullable=False)
    fin = Column(UTC_DATETIME, nullable=False)
    cupo_total = Column(Integer, nullable=False)
    estado = Column(String(20), nullable=False, default="ACTIVO")
    actividad = relationship("ActividadDB")


RESERVA_RECURSO_CHECK = """
    (tipo = 'HOTEL' AND habitacion_id IS NOT NULL AND turno_id IS NULL
     AND fecha_desde IS NOT NULL AND fecha_hasta IS NOT NULL
     AND fecha_desde < fecha_hasta
     AND cantidad_habitaciones IS NOT NULL AND cantidad_habitaciones > 0)
    OR
    (tipo = 'ACTIVIDAD' AND turno_id IS NOT NULL AND habitacion_id IS NULL
     AND fecha_desde IS NULL AND fecha_hasta IS NULL
     AND cantidad_habitaciones IS NULL)
"""


class ReservaDB(Base):
    __tablename__ = "reservas"
    __table_args__ = (
        CheckConstraint(RESERVA_RECURSO_CHECK, name="CK_reservas_recurso"),
        CheckConstraint("tipo IN ('HOTEL', 'ACTIVIDAD')", name="CK_reservas_tipo"),
        CheckConstraint("estado IN ('PENDIENTE_PAGO', 'CONFIRMADA', 'CANCELADA', 'EXPIRADA')", name="CK_reservas_estado"),
        CheckConstraint("personas > 0", name="CK_reservas_personas"),
        CheckConstraint("precio_unitario > 0 AND total > 0", name="CK_reservas_importes"),
        CheckConstraint("moneda = 'ARS'", name="CK_reservas_moneda"),
        CheckConstraint("estado <> 'PENDIENTE_PAGO' OR vence_en IS NOT NULL", name="CK_reservas_vencimiento"),
        CheckConstraint("vence_en IS NULL OR vence_en > creado_en", name="CK_reservas_plazo"),
        UniqueConstraint("id", "total", "moneda", name="UQ_reservas_importe"),
        Index("IX_reservas_turista", "turista_id", "estado"),
        Index("IX_reservas_disponibilidad_hotel", "habitacion_id", "estado", "fecha_desde", "fecha_hasta"),
        Index("IX_reservas_disponibilidad_turno", "turno_id", "estado"),
    )

    id = Column(Integer, primary_key=True)
    turista_id = Column(Integer, ForeignKey("usuarios.id", name="FK_reservas_turista"), nullable=False)
    tipo = Column(String(20), nullable=False)
    habitacion_id = Column(Integer, ForeignKey("habitaciones.id", name="FK_reservas_habitacion"))
    turno_id = Column(Integer, ForeignKey("actividad_turnos.id", name="FK_reservas_turno"))
    fecha_desde = Column(Date)
    fecha_hasta = Column(Date)
    cantidad_habitaciones = Column(Integer)
    personas = Column(Integer, nullable=False)
    precio_unitario = Column(Numeric(12, 2), nullable=False)
    total = Column(Numeric(12, 2), nullable=False)
    moneda = Column(String(3), nullable=False, default="ARS")
    estado = Column(String(20), nullable=False, default="PENDIENTE_PAGO")
    creado_en = Column(UTC_DATETIME, nullable=False, default=utc_now)
    vence_en = Column(UTC_DATETIME)
    cancelada_en = Column(UTC_DATETIME)
    turista = relationship("UsuarioDB")
    habitacion = relationship("HabitacionDB")
    turno = relationship("ActividadTurnoDB")


class PagoDB(Base):
    __tablename__ = "pagos"
    __table_args__ = (
        ForeignKeyConstraint(
            ["reserva_id", "importe", "moneda"],
            ["reservas.id", "reservas.total", "reservas.moneda"],
            name="FK_pagos_reserva_importe",
        ),
        UniqueConstraint("clave_idempotencia", name="UQ_pagos_idempotencia"),
        CheckConstraint("estado IN ('APROBADO', 'RECHAZADO')", name="CK_pagos_estado"),
        CheckConstraint("importe > 0", name="CK_pagos_importe"),
        CheckConstraint("moneda = 'ARS'", name="CK_pagos_moneda"),
        Index(
            "UX_pagos_reserva_aprobada", "reserva_id", unique=True,
            mssql_where=text("estado = 'APROBADO'"),
            sqlite_where=text("estado = 'APROBADO'"),
        ),
        Index("IX_pagos_reserva", "reserva_id"),
    )

    id = Column(Integer, primary_key=True)
    reserva_id = Column(Integer, nullable=False)
    clave_idempotencia = Column(String(64), nullable=False)
    importe = Column(Numeric(12, 2), nullable=False)
    moneda = Column(String(3), nullable=False, default="ARS")
    estado = Column(String(20), nullable=False)
    creado_en = Column(UTC_DATETIME, nullable=False, default=utc_now)
    reserva = relationship("ReservaDB")
