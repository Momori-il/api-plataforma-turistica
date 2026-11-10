"""Guarded read/cleanup helpers for Macro 3's dedicated integration DB only."""
import hashlib
import json
import sys
from pathlib import Path
from sqlalchemy import create_engine,text
from sqlalchemy.exc import DBAPIError
import config
from database.connection import engine,DATABASE_URL,SessionLocal
from models import UsuarioDB,ReservaDB,PagoDB
from models.request_idempotency import RequestIdempotencyDB
from models.messaging import OutboxEventDB,InboxEventDB,AuditEventDB,NotificationDB
from scripts.ae4_preservation import snapshot,check_constraints,DOMAIN_TABLES

def guard():
    if (config.DB_SERVER,config.DB_NAME,config.DB_USER)!=('sqlserver','TurismoPosadas_AE4_Integration','sa'):
        raise RuntimeError('Validation refuses non-isolated SQL')

def events_for(db,ids):
    payments=db.query(PagoDB.id).filter(PagoDB.reserva_id.in_(ids)).all()
    keys=[f'reserva:{x}' for x in ids]+[f'pago:{p[0]}' for p in payments]
    return db.query(OutboxEventDB).filter(OutboxEventDB.aggregate_key.in_(keys)).all()

def transaction_snapshot(db):
    result={}
    for name in DOMAIN_TABLES:
        key='event_id' if name=='eventos_procesados' else 'id'
        rows=[dict(r) for r in db.execute(text(f'SELECT * FROM dbo.[{name}] ORDER BY [{key}]')).mappings()]
        result[name]={'count':len(rows),'sha256':hashlib.sha256(json.dumps(rows,sort_keys=True,default=str).encode()).hexdigest()}
    return result

def run(data):
    guard();action=data['action']
    if action=='snapshot':return {'snapshot':snapshot(engine),'dbcc_violations':check_constraints(engine)}
    if action=='actors':
        with SessionLocal() as db:return [{'id':x.id,'role':x.rol} for x in db.query(UsuarioDB).filter_by(activo=True)]
    if action=='permissions':
        password=Path('/run/secrets/sql_read_password').read_text(encoding='utf-8').strip()
        readonly=create_engine(DATABASE_URL.set(username='ae4_read',password=password),hide_parameters=True)
        blocked=0
        try:
            for sql in ['UPDATE dbo.hoteles SET nombre=nombre WHERE 1=0','SELECT password_hash FROM dbo.usuarios']:
                with readonly.connect() as db:
                    try:db.execute(text(sql))
                    except DBAPIError as exc:
                        if not any(code in str(exc.orig) for code in ('(229)','(230)')):raise
                        blocked+=1
                    finally:db.rollback()
        finally:readonly.dispose()
        assert blocked==2
        return {'write_denied':True,'password_hash_read_denied':True}
    ids=data['ids'];assert isinstance(ids,list) and 1<=len(ids)<=10 and all(type(x)==int and x>0 for x in ids)
    with SessionLocal() as db:
        events=events_for(db,ids);event_ids=[x.event_id for x in events]
        if action=='inspect':
            return {'events':[{'id':x.event_id,'type':x.event_type,'status':x.status,'correlation_id':x.correlation_id,'traceparent':json.loads(x.envelope).get('traceparent')} for x in events],
                    'audit':db.query(AuditEventDB).filter(AuditEventDB.event_id.in_(event_ids)).count(),
                    'notifications':db.query(NotificationDB).filter(NotificationDB.event_id.in_(event_ids)).count(),
                    'expected_notifications':sum(x.event_type in {'reserva.confirmada','reserva.cancelada'} for x in events)}
        if action!='cleanup':raise ValueError('Unknown action')
        assert all(x.status=='PUBLISHED' for x in events)
        for rid in ids:
            key=data['keys'][str(rid)];assert key.startswith('macro3-')
            digest=hashlib.sha256(key.encode()).hexdigest()
            assert db.query(RequestIdempotencyDB).filter_by(reserva_id=rid,key_digest=digest).count()==1
            assert db.get(ReservaDB,rid).estado=='CANCELADA'
        for model in [InboxEventDB,AuditEventDB,NotificationDB,OutboxEventDB]:
            db.query(model).filter(model.event_id.in_(event_ids)).delete(synchronize_session=False)
        db.query(RequestIdempotencyDB).filter(RequestIdempotencyDB.reserva_id.in_(ids)).delete(synchronize_session=False)
        payments=db.query(PagoDB).filter(PagoDB.reserva_id.in_(ids)).delete(synchronize_session=False)
        reservations=db.query(ReservaDB).filter(ReservaDB.id.in_(ids)).delete(synchronize_session=False)
        assert transaction_snapshot(db)==data['expected'],'Cleanup would not restore baseline; rolling back'
        db.commit()
    return {'removed_reservations':reservations,'removed_payments':payments,'snapshot':snapshot(engine),'dbcc_violations':check_constraints(engine)}

if __name__=='__main__':print(json.dumps(run(json.load(sys.stdin))))
