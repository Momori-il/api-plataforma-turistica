"""Cálculo de inventario ocupado en intervalos [entrada, salida)."""

from collections import defaultdict

from sqlalchemy import and_, or_

from models import ReservaDB
from models.mvp import utc_now


def blocking_reservations(db, room_ids, start, end=None, *, now=None):
    if not room_ids:
        return []
    now = now if now is not None else utc_now()
    query = db.query(
        ReservaDB.habitacion_id, ReservaDB.fecha_desde, ReservaDB.fecha_hasta,
        ReservaDB.cantidad_habitaciones, ReservaDB.personas,
    ).filter(
        ReservaDB.tipo == "HOTEL", ReservaDB.habitacion_id.in_(room_ids),
        ReservaDB.fecha_hasta > start,
        or_(
            ReservaDB.estado == "CONFIRMADA",
            and_(ReservaDB.estado == "PENDIENTE_PAGO", ReservaDB.vence_en > now),
        ),
    )
    if end is not None:
        query = query.filter(ReservaDB.fecha_desde < end)
    return query.all()


def peak_occupancy(reservations, start, end=None):
    changes = defaultdict(int)
    for stay in reservations:
        arrival = max(start, stay.fecha_desde)
        departure = min(end, stay.fecha_hasta) if end is not None else stay.fecha_hasta
        if arrival < departure:
            changes[arrival] += stay.cantidad_habitaciones
            changes[departure] -= stay.cantidad_habitaciones
    occupied = peak = 0
    # Agrupar por fecha permite salidas y entradas contiguas sin doble ocupación.
    for day in sorted(changes):
        occupied += changes[day]
        peak = max(peak, occupied)
    return peak


def occupied_by_room(reservations, start, end):
    grouped = defaultdict(list)
    for stay in reservations:
        grouped[stay.habitacion_id].append(stay)
    return {room_id: peak_occupancy(stays, start, end) for room_id, stays in grouped.items()}
