"""Unit-of-work events: domain mutation and outbox use the same SQL commit."""
from datetime import timezone
import json
from uuid import uuid4

from sqlalchemy import event, func, inspect
from sqlalchemy.orm import Session
import config
from models import HotelDB, HabitacionDB, ActividadDB, ActividadTurnoDB, ReservaDB, PagoDB, UsuarioDB
from models.messaging import OutboxEventDB
from models.mvp import utc_now
from messaging.correlation import current
import observability as obs
from services.redis_support import invalidate, database_name

def namespaces(db, obj):
    if isinstance(obj, HotelDB):
        return [f"h:{obj.id}"]
    if isinstance(obj, HabitacionDB):
        return [f"h:{obj.hotel_id}"]
    if isinstance(obj, ActividadDB):
        return [f"a:{obj.id}"]
    if isinstance(obj, ActividadTurnoDB):
        return [f"a:{obj.actividad_id}"]
    if isinstance(obj, ReservaDB):
        resource = db.get(HabitacionDB, obj.habitacion_id) if obj.tipo == "HOTEL" else db.get(ActividadTurnoDB, obj.turno_id)
        return [f"h:{resource.hotel_id}"] if obj.tipo == "HOTEL" else [f"a:{resource.actividad_id}"]
    if isinstance(obj, UsuarioDB):
        return ([f"h:{x[0]}" for x in db.query(HotelDB.id).filter_by(prestador_id=obj.id)] +
                [f"a:{x[0]}" for x in db.query(ActividadDB.id).filter_by(prestador_id=obj.id)])
    return []

@obs.operation("outbox.enqueue")
def enqueue(db, event_type, aggregate_key, aggregate_id, payload):
    # Writers of the same domain aggregate already hold its SQL lock.
    sequence = (db.query(func.max(OutboxEventDB.sequence)).filter_by(aggregate_key=aggregate_key).scalar() or 0)
    pending = [e.sequence for e in db.new if isinstance(e, OutboxEventDB) and e.aggregate_key == aggregate_key]
    sequence = max([sequence, *pending]) + 1
    now, event_id = utc_now(), str(uuid4())
    obs.trace.get_current_span().set_attribute('event_id',event_id)
    envelope = dict(event_id=event_id, event_type=event_type, occurred_at=now.replace(tzinfo=timezone.utc).isoformat(),
                    correlation_id=current(), schema_version=1, aggregate_id=aggregate_id,
                    aggregate_version=sequence, payload=payload)
    envelope.update(obs.carrier())
    if event_type == "hotel.deactivated":
        envelope.update(event="HotelDeactivated", hotel_id=aggregate_id, timestamp=envelope["occurred_at"])
    db.add(OutboxEventDB(event_id=event_id, event_type=event_type, aggregate_key=aggregate_key,
                       sequence=sequence, correlation_id=envelope["correlation_id"],
                       envelope=json.dumps(envelope, ensure_ascii=False), routing_key=event_type,
                       occurred_at=now))

def reservation_event(db, obj, event_type, ns=None):
    ns = ns if ns is not None else namespaces(db, obj)
    payload = dict(reserva_id=obj.id, turista_id=obj.turista_id, tipo=obj.tipo,
                   habitacion_id=obj.habitacion_id, turno_id=obj.turno_id, personas=obj.personas,
                   cantidad_habitaciones=obj.cantidad_habitaciones,
                   fecha_desde=str(obj.fecha_desde) if obj.fecha_desde else None,
                   fecha_hasta=str(obj.fecha_hasta) if obj.fecha_hasta else None,
                   vence_en=obj.vence_en.replace(tzinfo=timezone.utc).isoformat() if obj.vence_en else None,
                   total=str(obj.total), moneda=obj.moneda, cache_namespaces=ns)
    enqueue(db, event_type, f"reserva:{obj.id}", obj.id, payload)
    db.info.setdefault("ae4_invalidate", set()).update(ns)

@event.listens_for(Session, "before_flush")
def collect(db, flush_context, instances):
    frames = []
    for obj in set(db.new) | set(db.dirty):
        if isinstance(obj, (OutboxEventDB,)) or not isinstance(obj, (HotelDB, HabitacionDB, ActividadDB, ActividadTurnoDB, ReservaDB, PagoDB, UsuarioDB)):
            continue
        is_new = obj in db.new
        if not is_new and not db.is_modified(obj, include_collections=False):
            continue
        old = inspect(obj).attrs.estado.history.deleted if hasattr(obj, "estado") else ()
        frames.append((obj, is_new, old[0] if old else None))
    db.info["ae4_frames"] = frames

@event.listens_for(Session, "after_flush_postexec")
def append_events(db, flush_context):
    for obj, is_new, old in db.info.pop("ae4_frames", []):
        ns = namespaces(db, obj)
        db.info.setdefault("ae4_invalidate", set()).update(ns)
        metric_type = ("reserva.creada" if is_new else "reserva.cancelada" if old != obj.estado and obj.estado == "CANCELADA" else None) if isinstance(obj,ReservaDB) else ("pago.aprobado" if obj.estado == "APROBADO" else "pago.rechazado") if isinstance(obj,PagoDB) and is_new else None
        if metric_type:db.info.setdefault("ae4_metrics",[]).append(metric_type)
        if not config.AE4_MESSAGING_ENABLED:
            continue
        if isinstance(obj, ReservaDB):
            event_type = "reserva.creada" if is_new else {
                "CONFIRMADA": "reserva.confirmada", "CANCELADA": "reserva.cancelada", "EXPIRADA": "reserva.expirada"
            }.get(obj.estado) if old != obj.estado else None
            if event_type:
                reservation_event(db, obj, event_type, ns)
        elif isinstance(obj, PagoDB) and is_new:
            enqueue(db, "pago.aprobado" if obj.estado == "APROBADO" else "pago.rechazado",
                    f"pago:{obj.id}", obj.id, dict(pago_id=obj.id, reserva_id=obj.reserva_id,
                    importe=str(obj.importe), moneda=obj.moneda, simulado=True))
        elif ns:
            enqueue(db, "catalogo.actualizado", f"{obj.__tablename__}:{obj.id}", obj.id,
                    {"cache_namespaces": ns})
            if isinstance(obj, HotelDB) and old == "ACTIVO" and obj.estado == "INACTIVO":
                enqueue(db, "hotel.deactivated", f"{obj.__tablename__}:{obj.id}", obj.id,
                        {"hotel_id": obj.id, "cache_namespaces": ns})

@event.listens_for(Session, "after_commit")
def after_commit(db):
    for event_type in db.info.pop("ae4_metrics",[]):obs.committed(event_type)
    ns = db.info.pop("ae4_invalidate", set())
    if ns:
        invalidate(ns, database_name(db))

@event.listens_for(Session, "after_rollback")
def after_rollback(db):
    db.info.pop("ae4_metrics", None)
    db.info.pop("ae4_frames", None)
    db.info.pop("ae4_invalidate", None)
