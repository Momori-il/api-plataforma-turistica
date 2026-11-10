"""Registro único de modelos para SQLAlchemy y las herramientas de esquema."""

from models.hotel import HotelDB
from models.viaje import ViajeDB, ViajeHotelDB
from models.evento_procesado import EventoProcesadoDB
from models.mvp import (
    UsuarioDB, HabitacionDB, ActividadDB, ActividadTurnoDB, ReservaDB, PagoDB,
)

__all__ = [
    "HotelDB", "ViajeDB", "ViajeHotelDB", "EventoProcesadoDB", "UsuarioDB",
    "HabitacionDB", "ActividadDB", "ActividadTurnoDB", "ReservaDB", "PagoDB", "RequestIdempotencyDB",
]

from models.request_idempotency import RequestIdempotencyDB
from models.messaging import OutboxEventDB, InboxEventDB, AuditEventDB, NotificationDB
