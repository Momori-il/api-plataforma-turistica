"""Disposable QA rows in the dedicated Docker integration database, never Windows."""
from datetime import timedelta
import json
import re
import sys

from sqlalchemy import text
from database.connection import SessionLocal, engine
from models import UsuarioDB, HotelDB, HabitacionDB, ActividadDB, ActividadTurnoDB, ReservaDB, PagoDB
from models.mvp import utc_now
from models.messaging import OutboxEventDB, InboxEventDB, AuditEventDB, NotificationDB
from models.request_idempotency import RequestIdempotencyDB
from scripts.container_checks import guard, transaction_snapshot
from scripts.ae4_preservation import check_constraints
from security import hash_password


def run(data):
    guard()
    tag = data['tag']
    assert re.fullmatch(r'macro4-[0-9a-f]{32}', tag)
    with SessionLocal() as db:
        if data['action'] == 'setup':
            before = transaction_snapshot(db)
            users = {}
            for role in ['ADMIN', 'PRESTADOR', 'TURISTA']:
                user = UsuarioDB(nombre='QA ' + role, email=f'{tag}-{role.lower()}@example.com',
                                 password_hash=hash_password(data['password']), rol=role, activo=True)
                db.add(user); db.flush(); users[role] = {'id': user.id, 'email': user.email, 'rol': role, 'nombre': user.nombre}
            hotel = HotelDB(nombre=tag, zona_id=1, direccion='Centro', descripcion='Fixture temporal QA',
                            servicio='WiFi', categoria=3, precio_base=100, estado='ACTIVO',
                            aprobacion='APROBADA', prestador_id=users['PRESTADOR']['id'])
            activity = ActividadDB(nombre=tag, ubicacion='Costanera', duracion_minutos=60, precio_persona=100,
                                   estado='ACTIVO', aprobacion='APROBADA', prestador_id=users['PRESTADOR']['id'])
            db.add_all([hotel, activity]); db.flush()
            room = HabitacionDB(hotel_id=hotel.id, nombre='QA doble', capacidad=2, cantidad_total=20, precio_noche=100)
            last_room = HabitacionDB(hotel_id=hotel.id, nombre='QA ultima', capacidad=2, cantidad_total=1, precio_noche=100)
            start = utc_now() + timedelta(days=90)
            turn = ActividadTurnoDB(actividad_id=activity.id, inicio=start, fin=start+timedelta(hours=1), cupo_total=20)
            last_turn = ActividadTurnoDB(actividad_id=activity.id, inicio=start+timedelta(days=1), fin=start+timedelta(days=1,hours=1), cupo_total=1)
            db.add_all([room,last_room,turn,last_turn]); db.flush()
            result = dict(tag=tag, users=users, hotel=hotel.id, room=room.id, last_room=last_room.id,
                          activity=activity.id, turn=turn.id, last_turn=last_turn.id, baseline=before,
                          fecha_desde=str(start.date()), fecha_hasta=str((start+timedelta(days=2)).date()))
            db.commit()
            return result
        f = data['fixture']
        assert f['tag'] == tag
        uids=[u['id'] for u in f['users'].values()]
        users=db.query(UsuarioDB).filter(UsuarioDB.id.in_(uids)).all()
        assert len(users)==3 and all(u.email.startswith(tag+'-') for u in users)
        assert db.get(HotelDB,f['hotel']).nombre == tag and db.get(ActividadDB,f['activity']).nombre == tag
        reservations=db.query(ReservaDB).filter(ReservaDB.turista_id==f['users']['TURISTA']['id']).all()
        assert len(reservations)<=200
        assert all(r.habitacion_id in [f['room'],f['last_room']] if r.tipo=='HOTEL' else r.turno_id in [f['turn'],f['last_turn']] for r in reservations)
        ids=[r.id for r in reservations]
        payments=db.query(PagoDB).filter(PagoDB.reserva_id.in_(ids)).all()
        aggregate_keys=[f'reserva:{r}' for r in ids]+[f'pago:{p.id}' for p in payments]
        events=db.query(OutboxEventDB).filter(OutboxEventDB.aggregate_key.in_(aggregate_keys)).all()
        if data['action']=='inspect':
            foreign_reservation=db.query(ReservaDB.id).filter(ReservaDB.turista_id!=f['users']['TURISTA']['id']).first()
            foreign_hotel=db.query(HotelDB.id).filter(HotelDB.prestador_id!=f['users']['PRESTADOR']['id']).first()
            event_ids=[e.event_id for e in events]
            audit_count=db.query(AuditEventDB).filter(AuditEventDB.event_id.in_(event_ids)).count()
            notification_count=db.query(NotificationDB).filter(NotificationDB.event_id.in_(event_ids)).count()
            return {'reservations':len(ids),'payments':len(payments),'states':[r.estado for r in reservations],
                    'pending_events':sum(e.status!='PUBLISHED' for e in events),
                    'pending_effects':len(events)-audit_count+sum(e.event_type in ['reserva.confirmada','reserva.cancelada'] for e in events)-notification_count,
                    'approved':sum(p.estado=='APROBADO' for p in payments),
                    'dbcc_violations':check_constraints(engine),
                    'foreign_reservation_id':foreign_reservation[0] if foreign_reservation else None,
                    'foreign_hotel_id':foreign_hotel[0] if foreign_hotel else None}
        assert data['action']=='cleanup'
        assert all(e.status=='PUBLISHED' for e in events), 'Wait for Outbox before cleanup'
        event_ids=[e.event_id for e in events]
        for model in [InboxEventDB,AuditEventDB,NotificationDB,OutboxEventDB]:
            db.query(model).filter(model.event_id.in_(event_ids)).delete(synchronize_session=False)
        db.query(RequestIdempotencyDB).filter(RequestIdempotencyDB.reserva_id.in_(ids)).delete(synchronize_session=False)
        db.query(PagoDB).filter(PagoDB.reserva_id.in_(ids)).delete(synchronize_session=False)
        db.query(ReservaDB).filter(ReservaDB.id.in_(ids)).delete(synchronize_session=False)
        db.query(ActividadTurnoDB).filter(ActividadTurnoDB.id.in_([f['turn'],f['last_turn']])).delete(synchronize_session=False)
        db.query(HabitacionDB).filter(HabitacionDB.id.in_([f['room'],f['last_room']])).delete(synchronize_session=False)
        db.delete(db.get(ActividadDB,f['activity']));db.delete(db.get(HotelDB,f['hotel']));db.flush()
        db.query(UsuarioDB).filter(UsuarioDB.id.in_(uids)).delete(synchronize_session=False)
        assert transaction_snapshot(db)==f['baseline'], 'Rollback: unrelated rows changed'
        db.commit()
        return {'removed_reservations':len(ids),'removed_payments':len(payments),
                'baseline_restored':True,'dbcc_violations':check_constraints(engine)}


if __name__=='__main__':
    print(json.dumps(run(json.load(sys.stdin))))
