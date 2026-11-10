"""Explicit real integration against a disposable SQL database and scoped broker queues.

Run: python -m scripts.validate_ae4 --real. Never runs seeds on TurismoPosadas.
Requires configured REDIS_URL / RABBITMQ_URL. Missing Redis does not skip SQL/AMQP evidence.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import hashlib
import json
from pathlib import Path
from threading import Barrier
import time
from uuid import uuid4
import secrets

from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlalchemy.orm import Session, sessionmaker
import config
from database.connection import engine, get_db
from main import app
from models import UsuarioDB, ReservaDB, PagoDB
from models.mvp import utc_now
from models.messaging import OutboxEventDB, InboxEventDB, AuditEventDB, NotificationDB
from models.request_idempotency import RequestIdempotencyDB
from security import hash_password
from schemas.habitacion import business_today
from services import redis_support
from messaging import rabbitmq, relay, worker
from scripts.ae4_preservation import snapshot, check_constraints
from tests.sqlserver_support import isolated_sqlserver
import pika

def run():
    before = snapshot(engine)
    check_constraints(engine)
    results = {"checks": [], "blocked": [], "demo_before": before}
    def checked(name, details=None):
        results["checks"].append({"name": name, "result": "passed", "details": details})
        print("PASS " + name, flush=True)
    def read_only(conn, cursor, statement, parameters, context, many):
        if not statement.lstrip().upper().startswith(("SELECT", "DBCC")):
            raise RuntimeError("Demo SQL writes prohibited by integration guard")
    event.listen(engine,"before_cursor_execute",read_only)
    previous = app.dependency_overrides.copy()
    config.AE4_MESSAGING_ENABLED = True
    tag = "ae4test" + uuid4().hex
    config.AE4_QUEUE_PREFIX = tag
    config.AE4_RETRY_DELAYS_MS = (20,40,60)
    rabbitmq.EXCHANGE_NAME = worker.EXCHANGE_NAME = relay.EXCHANGE_NAME = "turismo.events."+tag
    rabbitmq.QUEUE_NAME = tag+".legacy"
    connection = None
    try:
        with isolated_sqlserver() as scratch:
            factory = sessionmaker(bind=scratch,autoflush=False)
            dbname = scratch.url.database
            assert dbname.startswith("TurismoPosadas_Test_") and dbname != config.DB_NAME
            def override():
                with factory() as db:yield db
            app.dependency_overrides[get_db] = override
            api = TestClient(app)
            password = secrets.token_urlsafe(24)
            with factory() as db:
                for name,role in [("provider","PRESTADOR"),("admin","ADMIN"),("tourist","TURISTA"),("other","TURISTA")]:
                    db.add(UsuarioDB(nombre=name,email=name+"@example.com",password_hash=hash_password(password),rol=role))
                db.commit()
            headers={}
            for name,role in [("provider","PRESTADOR"),("admin","ADMIN"),("tourist","TURISTA"),("other","TURISTA")]:
                r=api.post('/auth/login',json={"email":name+"@example.com","password":password})
                assert r.status_code==200,r.text
                headers[name]={"Authorization":"Bearer "+r.json()['access_token']}
                me=api.get('/auth/me',headers=headers[name]);assert me.json()['rol']==role
            checked("roles_login_me")
            r=api.post('/api/v1/hoteles/',json=dict(nombre="Integracion hotel",zona_id=1,precio_base=100),headers=headers['provider'])
            assert r.status_code==201,r.text
            hotel=r.json()['id']
            r=api.post(f'/api/v1/hoteles/{hotel}/habitaciones/',json=dict(nombre="Doble",capacidad=2,cantidad_total=1,precio_noche=100),headers=headers['provider'])
            assert r.status_code==201,r.text
            room=r.json()['id']
            assert api.patch(f'/api/v1/hoteles/{hotel}/aprobacion',json=dict(aprobacion='APROBADA'),headers=headers['admin']).status_code==200
            r=api.post('/api/v1/actividades/',json=dict(nombre="Integracion actividad",ubicacion="Posadas",duracion_minutos=60,precio_persona=100),headers=headers['provider'])
            assert r.status_code==201,r.text
            activity=r.json()['id'];start=utc_now()+timedelta(days=30)
            r=api.post(f'/api/v1/actividades/{activity}/turnos/',json=dict(inicio=start.isoformat()+'Z',cupo_total=1),headers=headers['provider'])
            assert r.status_code==201,r.text
            turn=r.json()['id']
            assert api.patch(f'/api/v1/actividades/{activity}/aprobacion',json=dict(aprobacion='APROBADA'),headers=headers['admin']).status_code==200
            checked("provider_create_admin_approve")
            day=business_today()+timedelta(days=30)
            hotel_payload=dict(hotel_id=hotel,habitacion_id=room,fecha_desde=str(day),fecha_hasta=str(day+timedelta(days=2)),personas=1,cantidad_habitaciones=1)
            activity_payload=dict(actividad_id=activity,turno_id=turn,personas=1)
            cid=str(uuid4())
            def reserve(kind,payload,h=None):
                return api.post('/api/v1/reservas/'+kind,json=payload,headers=h or headers['tourist'])
            def cancel(rid):
                r=api.patch(f'/api/v1/reservas/{rid}/cancelar',headers=headers['tourist']);assert r.status_code==200,r.text
            for kind,payload in [('hotel',hotel_payload),('actividad',activity_payload)]:
                h={**headers['tourist'],'Idempotency-Key':str(uuid4()),'X-Correlation-ID':cid}
                first=reserve(kind,payload,h);second=reserve(kind,payload,h)
                assert first.status_code==second.status_code==201,(first.text,second.text)
                assert first.json()['id']==second.json()['id']
                assert reserve(kind,{**payload,'personas':2},h).status_code==409
                rid=first.json()['id']
                assert api.get(f'/api/v1/reservas/{rid}',headers=headers['other']).status_code==404
                with factory() as db:
                    row=db.query(OutboxEventDB).filter_by(aggregate_key=f'reserva:{rid}',event_type='reserva.creada').one()
                    assert row.correlation_id==cid
                cancel(rid);checked('sql_idempotency_'+kind,{"same_id":rid,"conflict":409})
            def race(request):
                barrier=Barrier(2)
                def one(i):barrier.wait(timeout=10);return request(i)
                with ThreadPoolExecutor(2) as pool:
                    fs=[pool.submit(one,i) for i in range(2)]
                    return [f.result(timeout=30) for f in fs]
            for kind,payload in [('hotel',hotel_payload),('actividad',activity_payload)]:
                replies=race(lambda i:reserve(kind,payload,headers['tourist' if i==0 else 'other']))
                assert sum(r.status_code==201 for r in replies)==1,[r.text for r in replies]
                assert all(r.status_code in (201,409,503) for r in replies)
                winner=next(r for r in replies if r.status_code==201)
                owner='tourist' if replies[0].status_code==201 else 'other'
                rid=winner.json()['id']
                assert api.patch(f'/api/v1/reservas/{rid}/cancelar',headers=headers[owner]).status_code==200
                checked('last_unit_'+kind,{"statuses":[r.status_code for r in replies],"created":1})
            # Redis is auxiliary: repeat the actual SQL race without any Redis lock.
            configured_redis=config.REDIS_URL
            try:
                config.REDIS_URL=''
                for kind,payload in [('hotel',hotel_payload),('actividad',activity_payload)]:
                    replies=race(lambda i:reserve(kind,payload,headers['tourist' if i==0 else 'other']))
                    assert sorted(r.status_code for r in replies)==[201,409],[r.text for r in replies]
                    winner=next(r for r in replies if r.status_code==201)
                    owner='tourist' if replies[0].status_code==201 else 'other'
                    assert api.patch(f"/api/v1/reservas/{winner.json()['id']}/cancelar",headers=headers[owner]).status_code==200
                    checked('sql_only_last_unit_'+kind,{'statuses':[r.status_code for r in replies]})
            finally:
                config.REDIS_URL=configured_redis
            h={**headers['tourist'],'Idempotency-Key':str(uuid4())}
            replies=race(lambda i:reserve('hotel',hotel_payload,h))
            for i,r in enumerate(replies):
                if r.status_code==503:replies[i]=reserve('hotel',hotel_payload,h)
            assert all(r.status_code==201 for r in replies),[r.text for r in replies]
            assert replies[0].json()['id']==replies[1].json()['id']
            rid=replies[0].json()['id']
            with factory() as db:
                digest=hashlib.sha256(h['Idempotency-Key'].encode()).hexdigest()
                assert db.query(RequestIdempotencyDB).filter_by(key_digest=digest).count()==1
            checked('concurrent_idempotency',{"created":1})
            payment=dict(clave_idempotencia=str(uuid4()),resultado='APROBADO')
            replies=race(lambda i:api.post(f'/api/v1/reservas/{rid}/pagos/simular',json=payment,headers=headers['tourist']))
            assert sorted(r.status_code for r in replies)==[200,201],[r.text for r in replies]
            with factory() as db:assert db.query(PagoDB).filter_by(reserva_id=rid,estado='APROBADO').count()==1
            cancel(rid);checked('concurrent_payment_and_cancellation_history')
            rid=reserve('hotel',hotel_payload).json()['id']
            payment=dict(clave_idempotencia=str(uuid4()),resultado='APROBADO')
            replies=race(lambda i:api.post(f'/api/v1/reservas/{rid}/pagos/simular',json=payment,headers=headers['tourist'])
                         if i==0 else api.patch(f'/api/v1/reservas/{rid}/cancelar',headers=headers['tourist']))
            assert replies[0].status_code in (201,409) and replies[1].status_code==200,[r.text for r in replies]
            with factory() as db:
                assert db.get(ReservaDB,rid).estado=='CANCELADA'
                assert db.query(PagoDB).filter_by(reserva_id=rid,estado='APROBADO').count()==(1 if replies[0].status_code==201 else 0)
            checked('concurrent_payment_vs_cancellation',{'statuses':[r.status_code for r in replies]})
            management=['/api/v1/hoteles/gestion',f'/api/v1/hoteles/{hotel}/habitaciones/gestion',
                        '/api/v1/actividades/gestion',f'/api/v1/actividades/{activity}/turnos/gestion',
                        '/api/v1/gestion/reservas',f'/api/v1/gestion/reservas/{rid}']
            for actor in ['provider','admin']:
                for path in management:
                    response=api.get(path,headers=headers[actor]);assert response.status_code==200,(path,response.text)
            for path in ['/api/v1/admin/usuarios',f'/api/v1/gestion/reservas/{rid}/pagos']:
                assert api.get(path,headers=headers['admin']).status_code==200
                assert api.get(path,headers=headers['provider']).status_code==403
            for path in [f'/api/v1/hoteles/{hotel}',f'/api/v1/actividades/{activity}',f'/api/v1/actividades/{activity}/turnos/']:
                assert api.get(path).status_code==200
            checked('public_and_manager_http_regression')
            query={k:v for k,v in hotel_payload.items() if k not in ('hotel_id','habitacion_id')}
            url=f'/api/v1/hoteles/{hotel}/habitaciones/disponibilidad'
            assert api.get(url,params=query).status_code==200
            saved_redis_url=config.REDIS_URL
            backend=redis_support.client()
            redis_ok=False
            try:redis_ok=backend is not None and backend.ping()
            except Exception:pass
            if redis_ok:
                from services.habitacion_service import HabitacionService
                redis_support.invalidate([f'h:{hotel}'],dbname)
                r=api.get(url,params=query);assert r.status_code==200 and r.json()['habitaciones']
                original=HabitacionService.availability_sql
                try:
                    def forbidden_compute(*args):raise AssertionError('cache HIT recalculated SQL')
                    HabitacionService.availability_sql=staticmethod(forbidden_compute)
                    assert api.get(url,params=query).status_code==200
                finally:HabitacionService.availability_sql=staticmethod(original)
                checked('real_redis_miss_hit')
                old_ttl=config.AVAILABILITY_CACHE_TTL_SECONDS;config.AVAILABILITY_CACHE_TTL_SECONDS=.15
                try:
                    redis_support.invalidate([f'h:{hotel}'],dbname)
                    assert api.get(url,params=query).status_code==200
                    keys=list(backend.scan_iter(match=redis_support.prefix(dbname)+f':avail:v1:h:{hotel}:g:*'))
                    fresh=[k for k in keys if 0<backend.pttl(k)<=150]
                    assert fresh
                    time.sleep(.2);assert all(backend.get(k) is None for k in fresh)
                finally:config.AVAILABILITY_CACHE_TTL_SECONDS=old_ttl
                checked('real_redis_ttl')
                r=reserve('hotel',hotel_payload);assert r.status_code==201,r.text
                assert not api.get(url,params=query).json()['habitaciones']
                cancel(r.json()['id']);assert api.get(url,params=query).json()['habitaciones']
                assert api.put(f'/api/v1/hoteles/{hotel}/habitaciones/{room}',json=dict(nombre='Doble',capacidad=2,cantidad_total=2,precio_noche=100),headers=headers['provider']).status_code==200
                assert api.get(url,params=query).json()['habitaciones'][0]['habitaciones_disponibles']==2
                checked('real_redis_invalidation')
                lease_key=f'{redis_support.prefix(dbname)}:lock:booking:room:{room}'
                old_wait=config.REDIS_LOCK_WAIT_SECONDS;old_lease=config.REDIS_LOCK_TTL_MS
                config.REDIS_LOCK_WAIT_SECONDS=0;config.REDIS_LOCK_TTL_MS=50
                try:
                    from fastapi import HTTPException
                    with redis_support.resource_lock(dbname,'room',room):
                        try:
                            with redis_support.resource_lock(dbname,'room',room):raise AssertionError('overlapping lock')
                        except HTTPException as exc:assert exc.status_code==503
                        time.sleep(.08)
                        assert backend.set(lease_key,'replacement-owner',nx=True,px=5000)
                    assert backend.get(lease_key)=='replacement-owner'
                    backend.delete(lease_key)
                finally:config.REDIS_LOCK_WAIT_SECONDS=old_wait;config.REDIS_LOCK_TTL_MS=old_lease
                checked('real_redis_lock_lease_and_owner')
            else:
                results['blocked'].append('Real Redis unavailable: cache HIT/TTL/locks not certified')
            config.REDIS_URL='redis://127.0.0.1:1/0'
            try:assert api.get(url,params=query).status_code==200
            finally:config.REDIS_URL=saved_redis_url
            checked('redis_connection_failure_sql_fallback')
            # Scoped broker topology; no production queue is consumed or purged.
            connection=rabbitmq.get_connection();channel=connection.channel()
            rabbitmq.configurar_canal(channel);channel.confirm_delivery()
            original_url=config.RABBITMQ_URL
            config.RABBITMQ_URL='amqp://localhost:1/%2F'
            try:assert relay.run_once(factory)
            finally:config.RABBITMQ_URL=original_url
            with factory() as db:
                assert db.query(OutboxEventDB).filter(OutboxEventDB.attempts>0,OutboxEventDB.published_at.is_(None)).count()>0
                db.query(OutboxEventDB).filter_by(status='PENDING').update({OutboxEventDB.available_at:utc_now()},synchronize_session=False);db.commit()
            for _ in range(1000):
                if not relay.run_once(factory):break
            with factory() as db:
                assert db.query(OutboxEventDB).filter(OutboxEventDB.published_at.is_(None)).count()==0
                total=db.query(OutboxEventDB).count()
                expected_notifications=db.query(OutboxEventDB).filter(OutboxEventDB.event_type.in_(['reserva.confirmada','reserva.cancelada'])).count()
                sample=db.query(OutboxEventDB).filter_by(event_type='reserva.creada').first().envelope
            checked('real_outbox_broker_failure_recovery_confirms',{"published":total})
            for consumer in ['audit','notifications']:
                while True:
                    m,p,b=channel.basic_get(queue=worker.queue_name(consumer),auto_ack=False)
                    if m is None:break
                    worker.handle(channel,m,p,b,consumer,factory)
                if consumer=='audit':
                    channel.basic_publish(exchange=rabbitmq.EXCHANGE_NAME,routing_key='reserva.creada',body=sample.encode(),mandatory=True,
                        properties=pika.BasicProperties(delivery_mode=2,content_type='application/json'))
                    m,p,b=channel.basic_get(queue=worker.queue_name(consumer),auto_ack=False)
                    assert m;worker.handle(channel,m,p,b,consumer,factory)
            with factory() as db:
                assert db.query(AuditEventDB).count()==total
                assert db.query(NotificationDB).count()==expected_notifications
                assert db.query(InboxEventDB).count()==total+expected_notifications
                assert db.query(AuditEventDB).filter_by(correlation_id=cid).count()>=2
            checked('real_inbox_duplicate_consumers_correlation',{"audit":total,"notifications":expected_notifications})
            if redis_ok:
                while True:
                    m,p,b=channel.basic_get(queue=worker.queue_name('availability'),auto_ack=False)
                    if m is None:break
                    worker.handle(channel,m,p,b,'availability',factory)
                checked('real_durable_cache_invalidation_consumer')
            poisoned=json.loads(sample);poisoned['event_id']=str(uuid4());body=json.dumps(poisoned).encode()
            channel.basic_publish(exchange='',routing_key=worker.queue_name('audit'),body=body,mandatory=True,
                properties=pika.BasicProperties(delivery_mode=2,content_type='application/json',message_id=poisoned['event_id']))
            attempts=0;end=time.monotonic()+10
            def failing(*args):raise RuntimeError('Controlled transient failure')
            while time.monotonic()<end:
                m,p,b=channel.basic_get(queue=worker.queue_name('audit'),auto_ack=False)
                if m:
                    worker.handle(channel,m,p,b,'audit',factory,processor=failing);attempts+=1
                m,p,b=channel.basic_get(queue=worker.queue_name('audit')+'.dlq',auto_ack=False)
                if m:
                    assert json.loads(b)['event_id']==poisoned['event_id'] and attempts==4
                    channel.basic_ack(delivery_tag=m.delivery_tag);break
                time.sleep(.02)
            else:raise AssertionError('DLQ delivery deadline exceeded')
            checked('real_retry_backoff_dlq',{"attempts":attempts})
            ready=api.get('/ready');assert ready.status_code==200,ready.text
            if redis_ok:assert ready.json()['status']=='ready',ready.text
            assert api.get('/health').status_code==200
            checked('real_readiness',ready.json())
            if redis_ok:
                own_prefix=redis_support.prefix(dbname)+':'
                keys=list(backend.scan_iter(match=own_prefix+'*'))
                assert all(k.startswith(own_prefix) for k in keys)
                if keys:backend.delete(*keys)
            api.close()
    finally:
        app.dependency_overrides.clear();app.dependency_overrides.update(previous)
        if connection and connection.is_open:
            ch=connection.channel()
            for consumer in ['audit','notifications','availability']:
                q=worker.queue_name(consumer);assert q.startswith(tag+'.')
                for name in [q,q+'.dlq',*[f'{q}.retry.{i}' for i in range(1,4)]]:ch.queue_delete(queue=name)
            ch.queue_delete(queue=rabbitmq.QUEUE_NAME)
            ch.exchange_delete(exchange=rabbitmq.EXCHANGE_NAME)
            connection.close()
        event.remove(engine,'before_cursor_execute',read_only)
    after=snapshot(engine);assert before==after,'Demo dataset changed'
    check_constraints(engine);results['demo_after']=after;results['dbcc_violations']=0
    checked('demo_preserved_exactly')
    return results

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--real',action='store_true')
    args=parser.parse_args()
    if not args.real:parser.error('Explicit --real required')
    report=run()
    path=Path(__file__).resolve().parents[2]/'docs/AE4_VALIDATION.json'
    existing=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    existing['integration']=report;path.write_text(json.dumps(existing,indent=2),encoding='utf-8')
    print(json.dumps({'passed':len(report['checks']),'blocked':report['blocked'],'evidence':str(path)}))

if __name__=='__main__':main()
