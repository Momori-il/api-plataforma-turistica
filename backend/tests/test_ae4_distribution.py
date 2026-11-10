"""Offline contracts. Real Redis/MSSQL/AMQP are tested by scripts.validate_ae4."""
import json
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4
import pytest
import redis
from fastapi import HTTPException
from sqlalchemy.orm import sessionmaker
import config
from models import ReservaDB
from models.messaging import OutboxEventDB, InboxEventDB, AuditEventDB, NotificationDB
from models.mvp import utc_now
from schemas.habitacion import DisponibilidadParams
from services.habitacion_service import HabitacionService
from services import redis_support
from messaging import relay, worker
from tests.test_reservas import bookings, create, cancel

class MemoryRedis:
    """Deterministic test adapter; Lua/server correctness is not inferred from it."""
    def __init__(self):
        self.data={}; self.clock=0; self.writes=[]
    def get(self,key):
        if key in self.data and self.data[key][1] is not None and self.data[key][1]<=self.clock:
            del self.data[key]
        return self.data.get(key,(None,None))[0]
    def set(self,key,value,nx=False,px=None):
        if nx and self.get(key) is not None:return False
        self.data[key]=(str(value),self.clock+px/1000 if px is not None else None)
        self.writes.append((key,px));return True
    def incr(self,key):
        n=int(self.get(key) or 0)+1;self.set(key,str(n));return n
    def eval(self,script,n,key,token):
        if self.get(key)!=token:return 0
        del self.data[key];return 1
    def ping(self):return True

@pytest.fixture
def distributed(bookings,monkeypatch):
    monkeypatch.setattr(config,"AE4_MESSAGING_ENABLED",True)
    backend=MemoryRedis();monkeypatch.setattr(redis_support,"client",lambda:backend)
    return bookings,backend

def params(e):return DisponibilidadParams(**{k:v for k,v in e['hotel_payload'].items() if k not in {'hotel_id','habitacion_id'}})

def test_cache_miss_hit_ttl_and_all_query_parameters(distributed,monkeypatch):
    e,b=distributed;p=params(e)
    real=HabitacionService.availability_sql;calls=[]
    def counted(*args):calls.append(1);return real(*args)
    monkeypatch.setattr(HabitacionService,'availability_sql',counted)
    first=HabitacionService.availability(e['db'],e['hotel'].id,p)
    assert HabitacionService.availability(e['db'],e['hotel'].id,p)==first
    assert len(calls)==1
    different=p.model_copy(update={'personas':1})
    HabitacionService.availability(e['db'],e['hotel'].id,different)
    assert len(calls)==2
    b.clock+=config.AVAILABILITY_CACHE_TTL_SECONDS+1
    HabitacionService.availability(e['db'],e['hotel'].id,p)
    assert len(calls)==3

def test_invalidate_reservation_cancel_and_inventory(distributed):
    e,b=distributed;p=params(e);hotel=e['hotel'].id
    assert HabitacionService.availability(e['db'],hotel,p).habitaciones
    response=create(e);assert response.status_code==201,response.text
    assert not HabitacionService.availability(e['db'],hotel,p).habitaciones
    assert cancel(e,response.json()['id']).status_code==200
    assert HabitacionService.availability(e['db'],hotel,p).habitaciones
    e['room'].cantidad_total=1;e['db'].commit()
    assert not HabitacionService.availability(e['db'],hotel,p).habitaciones

def test_cache_expiry_capped_by_pending_deadline(distributed):
    from datetime import timedelta
    e,b=distributed
    response=create(e);row=e['db'].get(ReservaDB,response.json()['id'])
    row.vence_en=utc_now()+timedelta(seconds=2);e['db'].commit()
    HabitacionService.availability(e['db'],e['hotel'].id,params(e))
    assert any(px and px<=2000 for key,px in b.writes if ':q:' in key)

def test_redis_failure_falls_back_to_sql(distributed,monkeypatch,caplog):
    e,_=distributed;b=MagicMock();b.get.side_effect=redis.ConnectionError('offline')
    monkeypatch.setattr(redis_support,'client',lambda:b)
    assert HabitacionService.availability(e['db'],e['hotel'].id,params(e)).habitaciones
    assert 'using_sql' in caplog.text

def test_lock_exclusion_expiry_and_owner(distributed,monkeypatch):
    _,b=distributed;monkeypatch.setattr(config,'REDIS_LOCK_WAIT_SECONDS',0)
    with redis_support.resource_lock('test','room',1):
        with pytest.raises(HTTPException) as caught:
            with redis_support.resource_lock('test','room',1):pass
        assert caught.value.status_code==503
        key=next(k for k in b.data if ':lock:' in k)
        b.clock+=config.REDIS_LOCK_TTL_MS/1000+1
        b.set(key,'new-owner',nx=True,px=5000)
    assert b.get(key)=='new-owner'  # Old finally must not release the new lease.

def test_outbox_atomic_replay_and_rollback(distributed,monkeypatch):
    e,_=distributed;h={**e['headers']['turista'],'Idempotency-Key':str(uuid4())}
    r=e['client'].post('/api/v1/reservas/hotel',json=e['hotel_payload'],headers=h)
    assert r.status_code==201,r.text
    assert e['client'].post('/api/v1/reservas/hotel',json=e['hotel_payload'],headers=h).json()['id']==r.json()['id']
    assert e['db'].query(OutboxEventDB).filter_by(event_type='reserva.creada').count()==1
    factory=sessionmaker(bind=e['db'].bind)
    from sqlalchemy import event
    def abort(db):raise RuntimeError('controlled commit failure')
    event.listen(factory.class_,'before_commit',abort)
    try:
        with factory() as db:
            from messaging.transactional import enqueue
            enqueue(db,'catalogo.actualizado','test:1',1,{'cache_namespaces':[]})
            db.flush()
            with pytest.raises(RuntimeError):db.commit()
            db.rollback()
    finally:event.remove(factory.class_,'before_commit',abort)
    assert e['db'].query(OutboxEventDB).filter_by(aggregate_key='test:1').count()==0

def test_relay_confirm_only_marks_after_success(distributed):
    e,_=distributed;assert create(e).status_code==201
    factory=sessionmaker(bind=e['db'].bind)
    def down(item):raise RuntimeError('broker down')
    assert relay.run_once(factory,down)
    row=e['db'].query(OutboxEventDB).populate_existing().one()
    assert row.published_at is None and row.attempts==1
    row.available_at=utc_now();e['db'].commit()
    sent=[];assert relay.run_once(factory,lambda item:sent.append(item))
    e['db'].expire_all();assert e['db'].get(OutboxEventDB,row.event_id).published_at
    assert len(sent)==1

def test_inbox_deduplicates_both_consumers(distributed):
    e,_=distributed;r=create(e)
    from messaging.transactional import reservation_event
    row=e['db'].get(ReservaDB,r.json()['id'])
    reservation_event(e['db'],row,'reserva.confirmada');e['db'].commit()
    event=e['db'].query(OutboxEventDB).filter_by(event_type='reserva.confirmada').one()
    factory=sessionmaker(bind=e['db'].bind)
    for consumer in ['audit','notifications']:
        assert worker.process(event.envelope.encode(),consumer,factory)
        assert not worker.process(event.envelope.encode(),consumer,factory)
    assert e['db'].query(InboxEventDB).count()==2
    assert e['db'].query(AuditEventDB).count()==1
    assert e['db'].query(NotificationDB).count()==1

@pytest.mark.parametrize('attempt,destination',[(0,'.retry.1'),(3,'.dlq')])
def test_retry_bounded_and_confirm_before_ack(attempt,destination):
    channel=MagicMock();properties=SimpleNamespace(headers={'x-ae4-attempt':attempt},message_id='x',correlation_id='x')
    def down(*args):raise RuntimeError('temporary')
    worker.handle(channel,SimpleNamespace(delivery_tag=1),properties,b'{}','audit',processor=down)
    assert channel.basic_publish.call_args.kwargs['routing_key'].endswith(destination)
    names=[call[0] for call in channel.mock_calls]
    assert names.index('basic_publish') < names.index('basic_ack')
    channel.basic_ack.assert_called_once()
    channel.reset_mock();channel.basic_publish.side_effect=RuntimeError('confirm lost')
    with pytest.raises(RuntimeError):worker.handle(channel,SimpleNamespace(delivery_tag=1),properties,b'{}','audit',processor=down)
    channel.basic_ack.assert_not_called()

def test_permanent_error_goes_directly_dlq():
    channel=MagicMock()
    worker.handle(channel,SimpleNamespace(delivery_tag=1),SimpleNamespace(headers={},message_id=None,correlation_id=None),b'invalid','audit')
    assert channel.basic_publish.call_args.kwargs['routing_key'].endswith('.dlq')

def test_ready_and_liveness_without_live_dependencies(monkeypatch):
    from services import readiness
    from fastapi.testclient import TestClient
    from main import app
    connection=MagicMock();engine=MagicMock();engine.connect.return_value=connection
    monkeypatch.setattr(readiness,'client',lambda:None)
    monkeypatch.setattr(readiness,'get_connection',lambda:(_ for _ in ()).throw(RuntimeError()))
    result=readiness.readiness(engine)
    assert result==dict(database='ok',redis='unavailable',rabbitmq='unavailable',status='degraded')
    engine.connect.side_effect=RuntimeError()
    assert readiness.readiness(engine)['status']=='unavailable'
    monkeypatch.setattr('main.engine',engine)
    with TestClient(app) as c:
        assert c.get('/health').status_code==200
        cid=str(uuid4());response=c.get('/health',headers={'X-Correlation-ID':cid})
        assert response.headers['X-Correlation-ID']==cid
        response=c.get('/ready')
        assert response.status_code==503
        assert response.json()['database']=='unavailable'
        assert set(response.json())=={'status','database','redis','rabbitmq'}

def test_outbox_failure_rolls_back_reservation_and_idempotency(distributed):
    from sqlalchemy import event
    from models.request_idempotency import RequestIdempotencyDB
    e,_=distributed
    def fail(mapper, connection, target):
        raise RuntimeError('Controlled outbox insert failure')
    event.listen(OutboxEventDB,'before_insert',fail)
    try:
        response=e['client'].post('/api/v1/reservas/hotel',json=e['hotel_payload'],
            headers={**e['headers']['turista'],'Idempotency-Key':str(uuid4())})
        assert response.status_code==500
    finally:
        event.remove(OutboxEventDB,'before_insert',fail)
    e['db'].rollback()
    assert e['db'].query(ReservaDB).count()==0
    assert e['db'].query(RequestIdempotencyDB).count()==0
    assert e['db'].query(OutboxEventDB).count()==0

def test_payment_events_no_duplicates_and_legacy_envelope(distributed):
    from tests.test_pagos import pay
    e,_=distributed;r=create(e);rid=r.json()['id']
    assert pay(e,rid,'RECHAZADO').status_code==201
    assert e['db'].query(OutboxEventDB).filter_by(event_type='reserva.confirmada').count()==0
    key=str(uuid4())
    assert pay(e,rid,key=key).status_code==201
    assert pay(e,rid,key=key).status_code==200
    for name in ['pago.rechazado','pago.aprobado','reserva.confirmada']:
        assert e['db'].query(OutboxEventDB).filter_by(event_type=name).count()==1
    e['hotel'].estado='INACTIVO';e['db'].commit()
    event=e['db'].query(OutboxEventDB).filter_by(event_type='hotel.deactivated').one()
    envelope=json.loads(event.envelope)
    assert envelope['event']=='HotelDeactivated'
    assert envelope['hotel_id']==e['hotel'].id
    assert envelope['timestamp']==envelope['occurred_at']

def test_relay_exhaustion_keeps_event_and_blocks_later_sequence(distributed,monkeypatch):
    e,_=distributed;assert create(e).status_code==201
    monkeypatch.setattr(config,'OUTBOX_MAX_ATTEMPTS',1)
    factory=sessionmaker(bind=e['db'].bind)
    def fail(item):raise RuntimeError('broker unavailable')
    assert relay.run_once(factory,fail)
    row=e['db'].query(OutboxEventDB).populate_existing().one()
    assert row.status=='FAILED' and row.published_at is None
    assert cancel(e,e['db'].query(ReservaDB).one().id).status_code==200
    assert relay.claim(factory) is None
    assert e['db'].query(OutboxEventDB).count()==2
