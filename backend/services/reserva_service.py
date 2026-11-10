from datetime import timedelta, timezone
from decimal import Decimal

from fastapi import HTTPException
import observability as obs
from sqlalchemy.orm import joinedload
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from hashlib import sha256
from models.request_idempotency import RequestIdempotencyDB

import config
from models import (
    ActividadDB, ActividadTurnoDB, HabitacionDB, HotelDB, ReservaDB,
)
from models.mvp import utc_now
from schemas.actividad import POSADAS_TZ
from schemas.reserva import ActividadReservada, AlojamientoReservado, ReservaPage, ReservaResponse
from services.actividad_service import ActividadService, cupos_ocupados
from services.disponibilidad_service import blocking_reservations, peak_occupancy
from services.hotel_service import HotelService
from services.redis_support import lock_reservation

MONEY_MAX = Decimal("9999999999.99")


class ReservaService:
    @staticmethod
    def tourist(actor):
        if not actor.activo or actor.rol != "TURISTA":
            raise HTTPException(403, "Solo TURISTA puede operar sus reservas")

    @staticmethod
    def lock_row(db, model, resource_id, **filters):
        query = db.query(model).filter(model.id == resource_id)
        for name, value in filters.items():
            query = query.filter(getattr(model, name) == value)
        row = query.with_hint(model, "WITH (UPDLOCK, HOLDLOCK)", dialect_name="mssql").populate_existing().first()
        if row is None:
            raise HTTPException(404, "Recurso no encontrado")
        return row

    @staticmethod
    def deadline(now, starts=None):
        if not 1 <= config.RESERVA_PAGO_MINUTOS <= 120:
            raise HTTPException(503, "Plazo de pago de reservas no configurado correctamente")
        end = now + timedelta(minutes=config.RESERVA_PAGO_MINUTOS)
        return min(end, starts) if starts is not None else end

    @staticmethod
    def money(unit_price, multiplier):
        total = (unit_price * multiplier).quantize(Decimal("0.01"))
        if not Decimal("0") < total <= MONEY_MAX:
            raise HTTPException(400, "El importe total excede el rango permitido")
        return total

    @staticmethod
    def idempotency(db, data, actor, operation, key):
        ReservaService.tourist(actor)
        if key is None:
            return None, None
        if not 1 <= len(key) <= 128 or not key.isascii() or any(ord(c) < 33 or ord(c) > 126 for c in key):
            raise HTTPException(400, "Idempotency-Key requiere entre 1 y 128 caracteres ASCII visibles")
        digest = sha256(key.encode()).hexdigest()
        fingerprint = sha256(data.model_dump_json().encode()).hexdigest()
        identity = (actor.id, operation, digest)
        if db.bind.dialect.name == "mssql":
            result = db.execute(text("SET NOCOUNT ON; DECLARE @r INT; EXEC @r=sys.sp_getapplock @Resource=:resource, @LockMode='Exclusive', @LockOwner='Transaction', @LockTimeout=2000; SET NOCOUNT OFF; SELECT @r"),
                                {"resource": f"pt:idempotency:{actor.id}:{operation}:{digest}"}).scalar()
            if result is None or result < 0:
                raise HTTPException(503, "Operación en curso; reintentá con la misma clave", headers={"Retry-After": "1"})
        try:
            record = db.get(RequestIdempotencyDB, identity, populate_existing=True)
        except ProgrammingError:
            db.rollback()
            raise HTTPException(503, "La migración técnica de idempotencia está pendiente") from None
        if record is not None:
            if record.request_digest != fingerprint:
                raise HTTPException(409, "La clave de idempotencia ya se utilizó con otros datos")
            return None, ReservaService.get(db, record.reserva_id, actor)
        return RequestIdempotencyDB(actor_id=actor.id, operation=operation,
                                    key_digest=digest, request_digest=fingerprint), None

    @staticmethod
    def save(db, reservation, idempotency_record=None):
        db.add(reservation)
        try:
            if idempotency_record is not None:
                db.flush()
                idempotency_record.reserva_id = reservation.id
                db.add(idempotency_record)
            db.commit()
        except Exception:
            db.rollback()
            raise
        db.refresh(reservation)
        return ReservaService.response(reservation)

    @staticmethod
    @obs.operation("reservation.hotel")
    @lock_reservation("room", "habitacion_id")
    def create_hotel(db, data, actor, idempotency_key=None):
        record, replay = ReservaService.idempotency(db, data, actor, "HOTEL", idempotency_key)
        if replay is not None:
            return replay
        ReservaService.lock_row(db, HotelDB, data.hotel_id)
        if HotelService.get_by_id(db, data.hotel_id) is None:
            raise HTTPException(404, "Publicación no disponible")
        room = ReservaService.lock_row(db, HabitacionDB, data.habitacion_id, hotel_id=data.hotel_id)
        if room.estado != "ACTIVO":
            raise HTTPException(404, "Habitación no publicada")
        now = utc_now()  # Después de esperar los bloqueos, no antes.
        today = now.replace(tzinfo=timezone.utc).astimezone(POSADAS_TZ).date()
        if data.fecha_desde < today:
            raise HTTPException(400, "La entrada no puede ser anterior a hoy")
        if data.personas > room.capacidad * data.cantidad_habitaciones:
            raise HTTPException(409, "La capacidad solicitada no alcanza para las personas")
        stays = blocking_reservations(db, [room.id], data.fecha_desde, data.fecha_hasta, now=now)
        occupied = peak_occupancy(stays, data.fecha_desde, data.fecha_hasta)
        if data.cantidad_habitaciones > room.cantidad_total - occupied:
            raise HTTPException(409, "No hay habitaciones suficientes para toda la estadía")
        nights = (data.fecha_hasta - data.fecha_desde).days
        reservation = ReservaDB(
            turista_id=actor.id, tipo="HOTEL", habitacion_id=room.id,
            fecha_desde=data.fecha_desde, fecha_hasta=data.fecha_hasta,
            cantidad_habitaciones=data.cantidad_habitaciones, personas=data.personas,
            precio_unitario=room.precio_noche,
            total=ReservaService.money(room.precio_noche, nights * data.cantidad_habitaciones),
            moneda="ARS", estado="PENDIENTE_PAGO", creado_en=now,
            vence_en=ReservaService.deadline(now),
        )
        return ReservaService.save(db, reservation, record)

    @staticmethod
    @obs.operation("reservation.activity")
    @lock_reservation("turn", "turno_id")
    def create_activity(db, data, actor, idempotency_key=None):
        record, replay = ReservaService.idempotency(db, data, actor, "ACTIVIDAD", idempotency_key)
        if replay is not None:
            return replay
        ReservaService.lock_row(db, ActividadDB, data.actividad_id)
        activity = ActividadService.public_get(db, data.actividad_id)
        turn = ReservaService.lock_row(db, ActividadTurnoDB, data.turno_id, actividad_id=data.actividad_id)
        if turn.estado != "ACTIVO":
            raise HTTPException(404, "Turno no publicado")
        now = utc_now()
        if turn.inicio <= now:
            raise HTTPException(409, "El turno ya comenzó")
        occupied = cupos_ocupados(db, [turn.id], now=now).get(turn.id, 0)
        if data.personas > turn.cupo_total - occupied:
            raise HTTPException(409, "No hay cupos suficientes en el turno")
        reservation = ReservaDB(
            turista_id=actor.id, tipo="ACTIVIDAD", turno_id=turn.id, personas=data.personas,
            precio_unitario=activity.precio_persona,
            total=ReservaService.money(activity.precio_persona, data.personas),
            moneda="ARS", estado="PENDIENTE_PAGO", creado_en=now,
            vence_en=ReservaService.deadline(now, turn.inicio),
        )
        return ReservaService.save(db, reservation, record)

    @staticmethod
    def own_query(db, actor):
        ReservaService.tourist(actor)
        return db.query(ReservaDB).filter(ReservaDB.turista_id == actor.id)

    @staticmethod
    def eager(query):
        return query.options(
            joinedload(ReservaDB.habitacion).joinedload(HabitacionDB.hotel),
            joinedload(ReservaDB.turno).joinedload(ActividadTurnoDB.actividad),
        )

    @staticmethod
    def expire(db, *, user_id=None, reservation_id=None, now=None):
        now = now if now is not None else utc_now()
        query = db.query(ReservaDB).filter(ReservaDB.estado == "PENDIENTE_PAGO", ReservaDB.vence_en <= now)
        if user_id is not None:
            query = query.filter(ReservaDB.turista_id == user_id)
        if reservation_id is not None:
            query = query.filter(ReservaDB.id == reservation_id)
        from sqlalchemy import update
        # OUTPUT/RETURNING captures only transitions actually won by this UPDATE.
        ids = list(db.execute(update(ReservaDB).where(*query.whereclause.clauses).values(
            estado="EXPIRADA").returning(ReservaDB.id).execution_options(synchronize_session=False)).scalars())
        changed = len(ids)
        if changed:
            if config.AE4_MESSAGING_ENABLED:
                from messaging.transactional import reservation_event
                for rid in ids:
                    row = db.get(ReservaDB, rid, populate_existing=True)
                    reservation_event(db, row, "reserva.expirada")
            db.commit()
            db.expire_all()
        return changed

    @staticmethod
    def get(db, reservation_id, actor):
        ReservaService.tourist(actor)
        ReservaService.expire(db, user_id=actor.id, reservation_id=reservation_id)
        reservation = ReservaService.eager(ReservaService.own_query(db, actor)).filter(ReservaDB.id == reservation_id).populate_existing().first()
        if reservation is None:
            raise HTTPException(404, "Reserva no encontrada")
        return ReservaService.response(reservation)

    @staticmethod
    def list(db, params, actor):
        ReservaService.tourist(actor)
        ReservaService.expire(db, user_id=actor.id)
        query = ReservaService.own_query(db, actor)
        if params.estado is not None:
            query = query.filter(ReservaDB.estado == params.estado)
        if params.tipo is not None:
            query = query.filter(ReservaDB.tipo == params.tipo)
        count = query.count()
        rows = ReservaService.eager(query).order_by(ReservaDB.id.desc()).offset(params.offset).limit(params.limit).populate_existing().all()
        return ReservaPage(items=[ReservaService.response(row) for row in rows], total=count, offset=params.offset, limit=params.limit)

    @staticmethod
    def lock_owned(db, reservation_id, actor):
        """Orden compartido por cancelación y pago: publicación -> inventario -> reserva."""
        reservation = ReservaService.own_query(db, actor).filter(ReservaDB.id == reservation_id).first()
        if reservation is None:
            raise HTTPException(404, "Reserva no encontrada")
        if reservation.tipo == "HOTEL":
            room = db.get(HabitacionDB, reservation.habitacion_id)
            ReservaService.lock_row(db, HotelDB, room.hotel_id)
            resource = ReservaService.lock_row(db, HabitacionDB, room.id)
        else:
            turn = db.get(ActividadTurnoDB, reservation.turno_id)
            ReservaService.lock_row(db, ActividadDB, turn.actividad_id)
            resource = ReservaService.lock_row(db, ActividadTurnoDB, turn.id)
        reservation = ReservaService.lock_row(db, ReservaDB, reservation_id, turista_id=actor.id)
        return reservation, resource

    @staticmethod
    @obs.operation("reservation.cancel")
    def cancel(db, reservation_id, actor):
        reservation, resource = ReservaService.lock_owned(db, reservation_id, actor)
        now = utc_now()
        if reservation.estado == "CANCELADA":
            return ReservaService.response(reservation)
        if reservation.estado == "PENDIENTE_PAGO" and reservation.vence_en <= now:
            reservation.estado = "EXPIRADA"
            ReservaService.save(db, reservation)
            raise HTTPException(409, "La reserva ya venció")
        if reservation.estado == "EXPIRADA":
            raise HTTPException(409, "La reserva ya venció")
        if reservation.estado == "CONFIRMADA":
            today = now.replace(tzinfo=timezone.utc).astimezone(POSADAS_TZ).date()
            started = reservation.fecha_desde < today if reservation.tipo == "HOTEL" else resource.inicio <= now
            if started:
                raise HTTPException(409, "No se puede cancelar un servicio que ya comenzó")
        reservation.estado = "CANCELADA"
        reservation.cancelada_en = now
        return ReservaService.save(db, reservation)

    @staticmethod
    def response(reservation):
        result = ReservaResponse.model_validate(reservation)
        if reservation.tipo == "HOTEL":
            room = reservation.habitacion
            result.alojamiento = AlojamientoReservado(hotel_id=room.hotel_id, hotel_nombre=room.hotel.nombre, habitacion_nombre=room.nombre)
        else:
            turn = reservation.turno
            result.actividad = ActividadReservada(
                actividad_id=turn.actividad_id, nombre=turn.actividad.nombre,
                inicio=turn.inicio.replace(tzinfo=timezone.utc), fin=turn.fin.replace(tzinfo=timezone.utc),
            )
        return result
