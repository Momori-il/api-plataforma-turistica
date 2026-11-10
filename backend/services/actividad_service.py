from datetime import datetime, time, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import BigInteger, and_, cast, func, or_, true
from sqlalchemy.exc import IntegrityError

from models import ActividadDB, ActividadTurnoDB, ReservaDB, UsuarioDB
from models.mvp import utc_now
from schemas.actividad import POSADAS_TZ, TurnoPublicResponse, TurnoSearchResponse


def cupos_ocupados(db, turn_ids, *, now=None):
    if not turn_ids:
        return {}
    now = now if now is not None else utc_now()
    rows = db.query(ReservaDB.turno_id, func.sum(cast(ReservaDB.personas, BigInteger))).filter(
        ReservaDB.tipo == "ACTIVIDAD", ReservaDB.turno_id.in_(turn_ids),
        or_(ReservaDB.estado == "CONFIRMADA", and_(ReservaDB.estado == "PENDIENTE_PAGO", ReservaDB.vence_en > now)),
    ).group_by(ReservaDB.turno_id).all()
    return {turn_id: int(people) for turn_id, people in rows}


class ActividadService:
    @staticmethod
    def _role(actor, *roles):
        if not actor.activo or actor.rol not in roles:
            raise HTTPException(403, "No tenés permisos para esta operación")

    @staticmethod
    def public_query(db):
        return db.query(ActividadDB).join(UsuarioDB, ActividadDB.prestador_id == UsuarioDB.id).filter(
            ActividadDB.estado == "ACTIVO", ActividadDB.aprobacion == "APROBADA",
            UsuarioDB.activo == true(), UsuarioDB.rol == "PRESTADOR",
        )

    @staticmethod
    def public_list(db):
        return ActividadService.public_query(db).order_by(ActividadDB.id).all()

    @staticmethod
    def public_get(db, activity_id):
        activity = ActividadService.public_query(db).filter(ActividadDB.id == activity_id).first()
        if activity is None:
            raise HTTPException(404, "Actividad no encontrada")
        return activity

    @staticmethod
    def managed_query(db, actor):
        ActividadService._role(actor, "PRESTADOR", "ADMIN")
        query = db.query(ActividadDB)
        return query.filter(ActividadDB.prestador_id == actor.id) if actor.rol == "PRESTADOR" else query

    @staticmethod
    def managed_get(db, activity_id, actor, *, lock=False):
        query = ActividadService.managed_query(db, actor).filter(ActividadDB.id == activity_id)
        if lock:
            query = query.with_hint(ActividadDB, "WITH (UPDLOCK, HOLDLOCK)", dialect_name="mssql")
        activity = query.populate_existing().first()
        if activity is None:
            raise HTTPException(404, "Actividad no encontrada")
        return activity

    @staticmethod
    def save(db, obj):
        db.commit()
        db.refresh(obj)
        return obj

    @staticmethod
    def create(db, data, actor):
        ActividadService._role(actor, "PRESTADOR")
        activity = ActividadDB(**data.model_dump(), prestador_id=actor.id, estado="ACTIVO", aprobacion="PENDIENTE")
        db.add(activity)
        return ActividadService.save(db, activity)

    @staticmethod
    def update(db, activity_id, data, actor):
        activity = ActividadService.managed_get(db, activity_id, actor, lock=True)
        for key, value in data.model_dump().items():
            if getattr(activity, key) != value:
                setattr(activity, key, value)
                activity.aprobacion = "PENDIENTE"
        return ActividadService.save(db, activity)

    @staticmethod
    def change_state(db, activity_id, state, actor):
        activity = ActividadService.managed_get(db, activity_id, actor, lock=True)
        if actor.rol != "ADMIN" and state == "ACTIVO":
            raise HTTPException(403, "Solo ADMIN puede reactivar una actividad")
        activity.estado = state
        return ActividadService.save(db, activity)

    @staticmethod
    def active_provider(db, user_id):
        user = db.query(UsuarioDB).filter(
            UsuarioDB.id == user_id, UsuarioDB.rol == "PRESTADOR", UsuarioDB.activo == true(),
        ).populate_existing().first()
        if user is None:
            raise HTTPException(409, "Se requiere un prestador activo")
        return user

    @staticmethod
    def approve(db, activity_id, approval, actor):
        ActividadService._role(actor, "ADMIN")
        activity = ActividadService.managed_get(db, activity_id, actor, lock=True)
        if approval == "APROBADA":
            ActividadService.active_provider(db, activity.prestador_id)
        activity.aprobacion = approval
        return ActividadService.save(db, activity)

    @staticmethod
    def assign_provider(db, activity_id, provider_id, actor):
        ActividadService._role(actor, "ADMIN")
        activity = ActividadService.managed_get(db, activity_id, actor, lock=True)
        ActividadService.active_provider(db, provider_id)
        if activity.prestador_id != provider_id:
            activity.prestador_id = provider_id
            activity.aprobacion = "PENDIENTE"
        return ActividadService.save(db, activity)

    @staticmethod
    def managed_turn(db, activity_id, turn_id, actor, *, lock=False):
        activity = ActividadService.managed_get(db, activity_id, actor, lock=lock)
        query = db.query(ActividadTurnoDB).filter(ActividadTurnoDB.actividad_id == activity_id, ActividadTurnoDB.id == turn_id)
        if lock:
            query = query.with_hint(ActividadTurnoDB, "WITH (UPDLOCK, HOLDLOCK)", dialect_name="mssql")
        turn = query.populate_existing().first()
        if turn is None:
            raise HTTPException(404, "Turno no encontrado")
        return activity, turn

    @staticmethod
    def managed_turns(db, activity_id, actor):
        ActividadService.managed_get(db, activity_id, actor)
        return db.query(ActividadTurnoDB).filter(ActividadTurnoDB.actividad_id == activity_id).order_by(ActividadTurnoDB.inicio, ActividadTurnoDB.id).all()

    @staticmethod
    def duplicate_start(db, activity_id, start, exclude_id=None):
        query = db.query(ActividadTurnoDB).filter(ActividadTurnoDB.actividad_id == activity_id, ActividadTurnoDB.inicio == start)
        if exclude_id is not None:
            query = query.filter(ActividadTurnoDB.id != exclude_id)
        return query.first() is not None

    @staticmethod
    def turn_times(data, duration, now):
        start = data.inicio.astimezone(timezone.utc).replace(tzinfo=None)
        if start <= now:
            raise HTTPException(400, "El turno debe comenzar en el futuro")
        try:
            end = start + timedelta(minutes=duration)
        except OverflowError:
            raise HTTPException(400, "El fin del turno está fuera del rango permitido")
        return start, end

    @staticmethod
    def save_turn(db, turn):
        activity_id, start, turn_id = turn.actividad_id, turn.inicio, turn.id
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            if ActividadService.duplicate_start(db, activity_id, start, turn_id):
                raise HTTPException(409, "Ya existe un turno en ese horario de inicio")
            raise
        db.refresh(turn)
        return turn

    @staticmethod
    def create_turn(db, activity_id, data, actor):
        activity = ActividadService.managed_get(db, activity_id, actor, lock=True)
        start, end = ActividadService.turn_times(data, activity.duracion_minutos, utc_now())
        if ActividadService.duplicate_start(db, activity_id, start):
            raise HTTPException(409, "Ya existe un turno en ese horario de inicio")
        turn = ActividadTurnoDB(actividad_id=activity_id, inicio=start, fin=end, cupo_total=data.cupo_total, estado="ACTIVO")
        db.add(turn)
        return ActividadService.save_turn(db, turn)

    @staticmethod
    def update_turn(db, activity_id, turn_id, data, actor):
        activity, turn = ActividadService.managed_turn(db, activity_id, turn_id, actor, lock=True)
        now = utc_now()
        if turn.inicio <= now:
            raise HTTPException(409, "No se puede editar un turno que ya comenzó")
        start, end = ActividadService.turn_times(data, activity.duracion_minutos, now)
        if start == turn.inicio:
            end = turn.fin  # Duración del turno conservada si solo se modifica cupo.
        occupied = cupos_ocupados(db, [turn.id], now=now).get(turn.id, 0)
        if data.cupo_total < occupied:
            raise HTTPException(409, "El cupo no puede ser menor que las plazas reservadas vigentes")
        if occupied and (start != turn.inicio or end != turn.fin):
            raise HTTPException(409, "No se puede reprogramar un turno con reservas vigentes")
        if ActividadService.duplicate_start(db, activity_id, start, turn.id):
            raise HTTPException(409, "Ya existe un turno en ese horario de inicio")
        turn.inicio, turn.fin, turn.cupo_total = start, end, data.cupo_total
        return ActividadService.save_turn(db, turn)

    @staticmethod
    def change_turn_state(db, activity_id, turn_id, state, actor):
        _, turn = ActividadService.managed_turn(db, activity_id, turn_id, actor, lock=True)
        if state == "ACTIVO" and turn.inicio <= utc_now():
            raise HTTPException(409, "No se puede activar un turno que ya comenzó")
        turn.estado = state
        return ActividadService.save_turn(db, turn)

    @staticmethod
    def quote(activity, turn, people, occupied):
        available = max(0, turn.cupo_total - occupied)
        return TurnoPublicResponse(
            id=turn.id, actividad_id=turn.actividad_id,
            inicio=turn.inicio.replace(tzinfo=timezone.utc), fin=turn.fin.replace(tzinfo=timezone.utc),
            cupos_disponibles=available, personas=people,
            precio_persona=activity.precio_persona, precio_total=activity.precio_persona * people,
            disponible=available >= people,
        )

    @staticmethod
    def public_turn(db, activity_id, turn_id, people):
        activity = ActividadService.public_get(db, activity_id)
        now = utc_now()
        turn = db.query(ActividadTurnoDB).filter(
            ActividadTurnoDB.actividad_id == activity_id, ActividadTurnoDB.id == turn_id,
            ActividadTurnoDB.estado == "ACTIVO", ActividadTurnoDB.inicio > now,
        ).first()
        if turn is None:
            raise HTTPException(404, "Turno no encontrado")
        occupied = cupos_ocupados(db, [turn.id], now=now).get(turn.id, 0)
        return ActividadService.quote(activity, turn, people, occupied)

    @staticmethod
    def search_turns(db, activity_id, params, *, available_only=False):
        activity = ActividadService.public_get(db, activity_id)
        now = utc_now()
        start = datetime.combine(params.fecha_desde, time.min, tzinfo=POSADAS_TZ).astimezone(timezone.utc).replace(tzinfo=None)
        end = datetime.combine(params.fecha_hasta, time.min, tzinfo=POSADAS_TZ).astimezone(timezone.utc).replace(tzinfo=None)
        turns = db.query(ActividadTurnoDB).filter(
            ActividadTurnoDB.actividad_id == activity_id, ActividadTurnoDB.estado == "ACTIVO",
            ActividadTurnoDB.inicio > now, ActividadTurnoDB.inicio >= start, ActividadTurnoDB.inicio < end,
        ).order_by(ActividadTurnoDB.inicio, ActividadTurnoDB.id).all()
        occupied = cupos_ocupados(db, [turn.id for turn in turns], now=now)
        quotes = [ActividadService.quote(activity, turn, params.personas, occupied.get(turn.id, 0)) for turn in turns]
        if available_only:
            quotes = [quote for quote in quotes if quote.disponible]
        return TurnoSearchResponse(
            actividad_id=activity_id, fecha_desde=params.fecha_desde, fecha_hasta=params.fecha_hasta,
            personas=params.personas, turnos=quotes,
        )
